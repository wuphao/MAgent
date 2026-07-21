#!/usr/bin/env python3
"""Import longitudinal ADAS-Cog summary scores into RWE form 59.

PostgreSQL is used only for read-only patient-number lookup. Every form read
and write is performed through the RWE API. Dry-run is the default; pass
--commit to insert or update records.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_CSV_PATH = Path(r"C:\Users\admin\Downloads\ADAS_22Jun2026.csv")
DEFAULT_PROJECT_ID = 8
DEFAULT_FORM_ID = 59
DEFAULT_API_BASE_URL = "http://localhost:8080"
DEFAULT_DB_HOST = "localhost"
DEFAULT_DB_PORT = 5432
DEFAULT_DB_NAME = "rwe_nexus_develop"
DEFAULT_DB_USER = "postgres"
DEFAULT_DB_PASSWORD = "12345678"
DEFAULT_RWE_TOKEN = (
    "Bearer "
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJjbGFpbXMiOnsicm9sZSI6ImRvY3RvciIsInBob25lIjoiMTMwMjAzOTczNjYiLCJuYW1lIjoid3BoIiwiaWQiOjJ9LCJleHAiOjE3ODQ5NjM2MjB9."
    "N-I8dEEc0gKVAm6_Lsz8tmU5Pb90wvyJzpKZKVNJxqc"
)


class ImportFailure(RuntimeError):
    """Expected, user-facing import failure."""


@dataclass(frozen=True)
class AdasRow:
    source_row: int
    ptid: str
    rid: str
    phase: str
    viscode2: str
    visit_date: str
    totscore: float | None
    total13: float | None


@dataclass(frozen=True)
class PatientRef:
    patient_number: str
    patient_id: int


@dataclass
class ResultRow:
    ptid: str
    patient_id: int | None
    visit_date: str
    viscode2: str
    status: str
    message: str = ""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import ADAS-Cog 11/13 scores into the RWE multi-fill form.",
    )
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV_PATH)
    parser.add_argument("--project-id", type=int, default=DEFAULT_PROJECT_ID)
    parser.add_argument("--form-id", type=int, default=DEFAULT_FORM_ID)
    parser.add_argument("--patient-number", help="Only process this PTID.")
    parser.add_argument("--api-base-url", default=DEFAULT_API_BASE_URL)
    parser.add_argument("--token", default=DEFAULT_RWE_TOKEN)
    parser.add_argument("--db-host", default=DEFAULT_DB_HOST)
    parser.add_argument("--db-port", type=int, default=DEFAULT_DB_PORT)
    parser.add_argument("--db-name", default=DEFAULT_DB_NAME)
    parser.add_argument("--db-user", default=DEFAULT_DB_USER)
    parser.add_argument("--db-password", default=DEFAULT_DB_PASSWORD)
    parser.add_argument(
        "--on-existing",
        choices=("skip", "update", "error"),
        default="skip",
        help="Action for an existing patient_id + visit date record.",
    )
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--commit", action="store_true", help="Actually call insertData/updateData.")
    parser.add_argument("--report", type=Path, help="Optional JSON report output path.")
    return parser.parse_args()


def require_dependencies() -> tuple[Any, Any]:
    missing: list[str] = []
    try:
        import psycopg2
    except ImportError:
        psycopg2 = None
        missing.append("psycopg2-binary")
    try:
        import requests
    except ImportError:
        requests = None
        missing.append("requests")
    if missing:
        raise ImportFailure("缺少依赖，请先安装: " + " ".join(missing))
    return psycopg2, requests


def clean(value: Any) -> str:
    return "" if value is None else str(value).strip().strip("\ufeff")


def parse_date(value: Any, row_number: int) -> str:
    text = clean(value)
    if not text:
        raise ImportFailure(f"CSV 第 {row_number} 行 VISDATE 为空。")
    for pattern in ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y", "%Y%m%d"):
        try:
            return datetime.strptime(text, pattern).strftime("%Y-%m-%d")
        except ValueError:
            pass
    raise ImportFailure(f"CSV 第 {row_number} 行 VISDATE 格式无法识别: {text}")


def parse_score(value: Any, label: str, maximum: float, row_number: int) -> float | None:
    text = clean(value)
    if not text:
        return None
    try:
        score = float(text)
    except ValueError as exc:
        raise ImportFailure(f"CSV 第 {row_number} 行 {label} 不是数字: {text}") from exc
    if not math.isfinite(score) or not 0 <= score <= maximum:
        raise ImportFailure(f"CSV 第 {row_number} 行 {label} 超出 0～{maximum:g}: {score}")
    return score


def load_csv(path: Path) -> tuple[list[AdasRow], list[ResultRow]]:
    if not path.is_file():
        raise ImportFailure(f"CSV 文件不存在: {path}")
    rows: list[AdasRow] = []
    rejected: list[ResultRow] = []
    required_columns = {"PTID", "VISDATE", "TOTSCORE", "TOTAL13"}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        columns = set(reader.fieldnames or [])
        missing_columns = sorted(required_columns - columns)
        if missing_columns:
            raise ImportFailure("CSV 缺少列: " + ", ".join(missing_columns))
        for row_number, raw in enumerate(reader, start=2):
            ptid = clean(raw.get("PTID"))
            if not ptid:
                rejected.append(ResultRow("", None, "", clean(raw.get("VISCODE2")), "FAILED", f"第 {row_number} 行 PTID 为空"))
                continue
            try:
                visit_date = parse_date(raw.get("VISDATE"), row_number)
                totscore = parse_score(raw.get("TOTSCORE"), "TOTSCORE", 70, row_number)
                total13 = parse_score(raw.get("TOTAL13"), "TOTAL13", 85, row_number)
            except ImportFailure as exc:
                rejected.append(ResultRow(ptid, None, clean(raw.get("VISDATE")), clean(raw.get("VISCODE2")), "FAILED", str(exc)))
                continue
            if totscore is None and total13 is None:
                rejected.append(ResultRow(ptid, None, visit_date, clean(raw.get("VISCODE2")), "EMPTY_SCORES", "两个总分均为空"))
                continue
            rows.append(
                AdasRow(
                    source_row=row_number,
                    ptid=ptid,
                    rid=clean(raw.get("RID")),
                    phase=clean(raw.get("PHASE")),
                    viscode2=clean(raw.get("VISCODE2")),
                    visit_date=visit_date,
                    totscore=totscore,
                    total13=total13,
                )
            )
    return rows, rejected


def reject_duplicate_source_keys(rows: list[AdasRow]) -> None:
    seen: dict[tuple[str, str], int] = {}
    duplicates: list[str] = []
    for row in rows:
        key = (row.ptid, row.visit_date)
        if key in seen:
            duplicates.append(f"{row.ptid}/{row.visit_date} (CSV 行 {seen[key]} 和 {row.source_row})")
        else:
            seen[key] = row.source_row
    if duplicates:
        raise ImportFailure("CSV 存在重复 PTID + VISDATE: " + "; ".join(duplicates[:10]))


def query_project_patients(args: argparse.Namespace, psycopg2: Any) -> dict[str, PatientRef]:
    sql = """
        SELECT TRIM(pp.patient_number), pp.patient_id
        FROM patient_project pp
        JOIN patient p ON p.id = pp.patient_id
        WHERE pp.project_id = %s
          AND pp.is_delete = 0
          AND p.is_delete = 0
          AND pp.patient_number IS NOT NULL
          AND TRIM(pp.patient_number) <> ''
        ORDER BY TRIM(pp.patient_number)
    """
    connection = psycopg2.connect(
        host=args.db_host,
        port=args.db_port,
        dbname=args.db_name,
        user=args.db_user,
        password=args.db_password,
        connect_timeout=10,
    )
    try:
        connection.set_session(readonly=True, autocommit=True)
        with connection.cursor() as cursor:
            cursor.execute(sql, (args.project_id,))
            records = cursor.fetchall()
    finally:
        connection.close()
    return {number: PatientRef(number, int(patient_id)) for number, patient_id in records}


def authorization_header(token: str) -> str:
    cleaned = clean(token)
    if not cleaned:
        raise ImportFailure("API Token 为空。")
    return cleaned if cleaned.lower().startswith("bearer ") else f"Bearer {cleaned}"


def api_post(requests: Any, args: argparse.Namespace, path: str, payload: dict[str, Any]) -> dict[str, Any]:
    url = f"{args.api_base_url.rstrip('/')}{path}"
    try:
        response = requests.post(
            url,
            json=payload,
            headers={"Authorization": authorization_header(args.token), "Content-Type": "application/json"},
            timeout=args.timeout,
        )
        response.raise_for_status()
        result = response.json()
    except requests.RequestException as exc:
        raise ImportFailure(f"API 请求失败 {path}: {exc}") from exc
    except ValueError as exc:
        raise ImportFailure(f"API 返回的不是合法 JSON: {path}") from exc
    if not isinstance(result, dict):
        raise ImportFailure(f"API 返回结构不正确: {path}")
    if result.get("code") != 0:
        raise ImportFailure(f"API 业务失败 {path}: {result.get('message', result)}")
    return result


def query_existing_for_patient(requests: Any, args: argparse.Namespace, patient_id: int) -> dict[str, dict[str, Any]]:
    result = api_post(
        requests,
        args,
        "/form/queryData",
        {
            "formId": args.form_id,
            "page": 0,
            "pageSize": 0,
            "criteria": [{"enName": "patient_id", "inputValue": patient_id, "isFuzzy": False}],
        },
    )
    existing: dict[str, dict[str, Any]] = {}
    for item in ((result.get("data") or {}).get("list") or []):
        raw_date = item.get("访视日期")
        try:
            visit_date = parse_date(raw_date, 0)
        except ImportFailure:
            continue
        if visit_date in existing:
            raise ImportFailure(f"患者 {patient_id} 在 {visit_date} 有多条既有表单记录。")
        existing[visit_date] = item
    return existing


def build_records(row: AdasRow, patient_id: int) -> dict[str, Any]:
    records: dict[str, Any] = {"patient_id": patient_id, "访视日期": row.visit_date}
    if row.totscore is not None:
        records["ADAS-Cog 11 项总分"] = row.totscore
    if row.total13 is not None:
        records["ADAS-Cog 13 项总分"] = row.total13
    return records


def normalized_number(value: Any) -> float | None:
    text = clean(value)
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def same_scores(existing: dict[str, Any], row: AdasRow) -> bool:
    return (
        normalized_number(existing.get("ADAS-Cog 11 项总分")) == row.totscore
        and normalized_number(existing.get("ADAS-Cog 13 项总分")) == row.total13
    )


def submit_row(
    requests: Any,
    args: argparse.Namespace,
    row: AdasRow,
    patient_id: int,
    existing: dict[str, Any] | None,
) -> str:
    records = build_records(row, patient_id)
    if existing is not None:
        record_id = existing.get("id")
        if same_scores(existing, row):
            return f"SKIPPED: 已存在相同记录 id={record_id}"
        if args.on_existing == "skip":
            return f"CONFLICT_SKIPPED: 已存在不同分数 id={record_id}"
        if args.on_existing == "error":
            raise ImportFailure(f"{row.ptid}/{row.visit_date} 已存在不同分数 id={record_id}")
        if not record_id:
            raise ImportFailure(f"{row.ptid}/{row.visit_date} 既有记录缺少 id")
        api_post(
            requests,
            args,
            "/form/updateData",
            {"id": int(record_id), "formId": args.form_id, "records": records},
        )
        return f"UPDATED: id={record_id}"

    api_post(requests, args, "/form/insertData", {"formId": args.form_id, "records": records})
    return "INSERTED"


def write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    args = parse_args()
    try:
        psycopg2, requests = require_dependencies()
        csv_rows, preliminary_results = load_csv(args.csv)
        patients = query_project_patients(args, psycopg2)

        if args.patient_number:
            wanted = args.patient_number.strip()
            csv_rows = [row for row in csv_rows if row.ptid == wanted]
            preliminary_results = [row for row in preliminary_results if row.ptid == wanted]
            if wanted not in patients:
                raise ImportFailure(f"项目 {args.project_id} 中找不到 patient_number={wanted}")
            if not csv_rows and not preliminary_results:
                raise ImportFailure(f"CSV 中找不到 PTID={wanted}")

        preliminary_results = [row for row in preliminary_results if row.ptid in patients]
        matched_rows = [row for row in csv_rows if row.ptid in patients]
        unmatched_rows = [row for row in csv_rows if row.ptid not in patients]
        reject_duplicate_source_keys(matched_rows)
        results = list(preliminary_results)

        grouped: dict[str, list[AdasRow]] = {}
        for row in matched_rows:
            grouped.setdefault(row.ptid, []).append(row)

        mode = "commit" if args.commit else "dry-run"
        print(f"ADAS {mode}: 匹配 {len(grouped)} 位患者、{len(matched_rows)} 条有效访视。")
        for index, ptid in enumerate(sorted(grouped), start=1):
            patient = patients[ptid]
            patient_rows = sorted(grouped[ptid], key=lambda row: (row.visit_date, row.source_row))
            print(f"[{index}/{len(grouped)}] {ptid} -> patient_id={patient.patient_id}, {len(patient_rows)} 条")
            try:
                existing_by_date = (
                    query_existing_for_patient(requests, args, patient.patient_id) if args.commit else {}
                )
                for row in patient_rows:
                    if not args.commit:
                        status = "READY"
                    else:
                        status = submit_row(
                            requests,
                            args,
                            row,
                            patient.patient_id,
                            existing_by_date.get(row.visit_date),
                        )
                    results.append(ResultRow(ptid, patient.patient_id, row.visit_date, row.viscode2, status))
                    print(f"  {row.visit_date} {row.viscode2 or '-'}: {status}")
            except ImportFailure as exc:
                message = str(exc)
                print(f"  ERROR: {message}", file=sys.stderr)
                for row in patient_rows:
                    if not any(r.ptid == ptid and r.visit_date == row.visit_date for r in results):
                        results.append(ResultRow(ptid, patient.patient_id, row.visit_date, row.viscode2, "FAILED", message))

        counts: dict[str, int] = {}
        for result in results:
            category = result.status.split(":", 1)[0]
            counts[category] = counts.get(category, 0) + 1
        report = {
            "mode": mode,
            "csv": str(args.csv),
            "project_id": args.project_id,
            "form_id": args.form_id,
            "matched_patients": len(grouped),
            "matched_valid_visits": len(matched_rows),
            "valid_visits_outside_project": len(unmatched_rows),
            "counts": counts,
            "results": [asdict(item) for item in results],
        }
        print(json.dumps({key: value for key, value in report.items() if key != "results"}, ensure_ascii=False, indent=2))
        if args.report:
            write_report(args.report, report)
            print(f"报告已写入: {args.report}")
        if not args.commit:
            print("DRY-RUN: 未调用 RWE 查询或写入接口；确认后添加 --commit。")
        failed = counts.get("FAILED", 0)
        return 2 if failed else 0
    except ImportFailure as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("ERROR: 用户取消。", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
