#!/usr/bin/env python3
"""Import longitudinal CDR records into RWE form 58.

The database is queried read-only for PTID -> patient_id. Form data is read
and written only through the RWE API. Dry-run is the default.
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


DEFAULT_CSV = Path(r"C:\Users\admin\Downloads\CDR_22Jun2026.csv")
DEFAULT_PROJECT_ID = 8
DEFAULT_FORM_ID = 58
DEFAULT_API_BASE_URL = "http://localhost:8080"
DEFAULT_DB_PASSWORD = "12345678"
DEFAULT_TOKEN = (
    "Bearer "
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJjbGFpbXMiOnsicm9sZSI6ImRvY3RvciIsInBob25lIjoiMTMwMjAzOTczNjYiLCJuYW1lIjoid3BoIiwiaWQiOjJ9LCJleHAiOjE3ODQ5NjM2MjB9."
    "N-I8dEEc0gKVAm6_Lsz8tmU5Pb90wvyJzpKZKVNJxqc"
)

DOMAIN_FIELDS = {
    "CDMEMORY": "记忆能力",
    "CDORIENT": "时间、地点及人物定向能力",
    "CDJUDGE": "判断和解决问题能力",
    "CDCOMMUN": "参与工作、购物、社交等社会事务的能力",
    "CDHOME": "家庭事务",
    "CDCARE": "个人护理",
}
SCORE_OPTIONS = {
    0.0: "正常",
    0.5: "可疑或极轻度损害",
    1.0: "轻度损害",
    2.0: "中度损害",
    3.0: "重度损害",
}
OPTION_FIELDS = tuple(DOMAIN_FIELDS.values())
NUMERIC_FIELDS = ("总体评分", "CDRSB总分")


class ImportFailure(RuntimeError):
    pass


@dataclass(frozen=True)
class CdrRow:
    source_row: int
    ptid: str
    viscode2: str
    visit_date: str
    domain_scores: dict[str, float | None]
    global_score: float | None
    cdrsb: float | None
    warnings: tuple[str, ...]


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
    warnings: tuple[str, ...] = ()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import CDR longitudinal records into RWE form 58.")
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--project-id", type=int, default=DEFAULT_PROJECT_ID)
    parser.add_argument("--form-id", type=int, default=DEFAULT_FORM_ID)
    parser.add_argument("--patient-number", help="Only process this PTID.")
    parser.add_argument("--api-base-url", default=DEFAULT_API_BASE_URL)
    parser.add_argument("--token", default=DEFAULT_TOKEN)
    parser.add_argument("--db-host", default="localhost")
    parser.add_argument("--db-port", type=int, default=5432)
    parser.add_argument("--db-name", default="rwe_nexus_develop")
    parser.add_argument("--db-user", default="postgres")
    parser.add_argument("--db-password", default=DEFAULT_DB_PASSWORD)
    parser.add_argument("--on-existing", choices=("skip", "update", "error"), default="skip")
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--commit", action="store_true")
    parser.add_argument("--report", type=Path)
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
        raise ImportFailure(f"CSV 第 {row_number} 行 VISDATE 为空")
    for pattern in ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y", "%Y%m%d"):
        try:
            return datetime.strptime(text, pattern).strftime("%Y-%m-%d")
        except ValueError:
            pass
    raise ImportFailure(f"CSV 第 {row_number} 行 VISDATE 格式无法识别: {text}")


def parse_number(value: Any, label: str, row_number: int, allowed: set[float] | None = None) -> float | None:
    text = clean(value)
    if not text:
        return None
    try:
        number = float(text)
    except ValueError as exc:
        raise ImportFailure(f"CSV 第 {row_number} 行 {label} 不是数字: {text}") from exc
    if not math.isfinite(number):
        raise ImportFailure(f"CSV 第 {row_number} 行 {label} 不是有限数值")
    if number == -1.0:
        return None
    if allowed is not None and number not in allowed:
        raise ImportFailure(f"CSV 第 {row_number} 行 {label} 不在允许值中: {number}")
    return number


def load_csv(path: Path) -> tuple[list[CdrRow], list[ResultRow]]:
    if not path.is_file():
        raise ImportFailure(f"CSV 文件不存在: {path}")
    required = {"PTID", "VISDATE", "CDGLOBAL", "CDRSB", *DOMAIN_FIELDS.keys()}
    rows: list[CdrRow] = []
    rejected: list[ResultRow] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = sorted(required - set(reader.fieldnames or []))
        if missing:
            raise ImportFailure("CSV 缺少列: " + ", ".join(missing))
        for row_number, raw in enumerate(reader, start=2):
            ptid = clean(raw.get("PTID"))
            viscode2 = clean(raw.get("VISCODE2"))
            if not ptid:
                rejected.append(ResultRow("", None, "", viscode2, "FAILED", f"第 {row_number} 行 PTID 为空"))
                continue
            try:
                visit_date = parse_date(raw.get("VISDATE"), row_number)
                domains = {
                    source: parse_number(raw.get(source), source, row_number, set(SCORE_OPTIONS))
                    for source in DOMAIN_FIELDS
                }
                global_score = parse_number(raw.get("CDGLOBAL"), "CDGLOBAL", row_number, set(SCORE_OPTIONS))
                cdrsb = parse_number(raw.get("CDRSB"), "CDRSB", row_number)
                if cdrsb is not None and not 0 <= cdrsb <= 18:
                    raise ImportFailure(f"CSV 第 {row_number} 行 CDRSB 超出 0～18: {cdrsb}")
            except ImportFailure as exc:
                rejected.append(ResultRow(ptid, None, clean(raw.get("VISDATE")), viscode2, "FAILED", str(exc)))
                continue

            values = [*domains.values(), global_score, cdrsb]
            if all(value is None for value in values):
                rejected.append(ResultRow(ptid, None, visit_date, viscode2, "EMPTY_SCORES", "所有临床评分均缺失或为 -1"))
                continue

            warnings: list[str] = []
            if all(value is not None for value in domains.values()) and cdrsb is not None:
                domain_sum = sum(value for value in domains.values() if value is not None)
                if abs(domain_sum - cdrsb) > 1e-6:
                    warnings.append(f"CDRSB={cdrsb:g} 与六领域和={domain_sum:g} 不一致，保留源 CDRSB")
            rows.append(CdrRow(row_number, ptid, viscode2, visit_date, domains, global_score, cdrsb, tuple(warnings)))
    return rows, rejected


def reject_duplicate_keys(rows: list[CdrRow]) -> None:
    seen: dict[tuple[str, str], int] = {}
    duplicates: list[str] = []
    for row in rows:
        key = (row.ptid, row.visit_date)
        if key in seen:
            duplicates.append(f"{row.ptid}/{row.visit_date} (行 {seen[key]}、{row.source_row})")
        else:
            seen[key] = row.source_row
    if duplicates:
        raise ImportFailure("本次数据存在重复 PTID + VISDATE: " + "; ".join(duplicates[:10]))


def query_patients(args: argparse.Namespace, psycopg2: Any) -> dict[str, PatientRef]:
    sql = """
        SELECT TRIM(pp.patient_number), pp.patient_id
        FROM patient_project pp JOIN patient p ON p.id=pp.patient_id
        WHERE pp.project_id=%s AND pp.is_delete=0 AND p.is_delete=0
          AND pp.patient_number IS NOT NULL AND TRIM(pp.patient_number)<>''
        ORDER BY TRIM(pp.patient_number)
    """
    connection = psycopg2.connect(
        host=args.db_host, port=args.db_port, dbname=args.db_name,
        user=args.db_user, password=args.db_password, connect_timeout=10,
    )
    try:
        connection.set_session(readonly=True, autocommit=True)
        with connection.cursor() as cursor:
            cursor.execute(sql, (args.project_id,))
            records = cursor.fetchall()
    finally:
        connection.close()
    return {number: PatientRef(number, int(patient_id)) for number, patient_id in records}


def auth_header(token: str) -> str:
    token = clean(token)
    if not token:
        raise ImportFailure("API Token 为空")
    return token if token.lower().startswith("bearer ") else f"Bearer {token}"


def api_post(requests: Any, args: argparse.Namespace, path: str, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        response = requests.post(
            f"{args.api_base_url.rstrip('/')}{path}", json=payload,
            headers={"Authorization": auth_header(args.token), "Content-Type": "application/json"},
            timeout=args.timeout,
        )
        response.raise_for_status()
        result = response.json()
    except requests.RequestException as exc:
        raise ImportFailure(f"API 请求失败 {path}: {exc}") from exc
    except ValueError as exc:
        raise ImportFailure(f"API 返回的不是合法 JSON: {path}") from exc
    if not isinstance(result, dict) or result.get("code") != 0:
        raise ImportFailure(f"API 业务失败 {path}: {result.get('message', result) if isinstance(result, dict) else result}")
    return result


def query_existing(requests: Any, args: argparse.Namespace, patient_id: int) -> dict[str, dict[str, Any]]:
    result = api_post(requests, args, "/form/queryData", {
        "formId": args.form_id, "page": 0, "pageSize": 0,
        "criteria": [{"enName": "patient_id", "inputValue": patient_id, "isFuzzy": False}],
    })
    records: dict[str, dict[str, Any]] = {}
    for item in ((result.get("data") or {}).get("list") or []):
        try:
            date = parse_date(item.get("访视日期"), 0)
        except ImportFailure:
            continue
        if date in records:
            raise ImportFailure(f"患者 {patient_id} 在 {date} 有多条既有 CDR 记录")
        records[date] = item
    return records


def build_records(row: CdrRow, patient_id: int) -> dict[str, Any]:
    records: dict[str, Any] = {"patient_id": patient_id, "访视日期": row.visit_date}
    for source, target in DOMAIN_FIELDS.items():
        score = row.domain_scores[source]
        if score is not None:
            records[target] = SCORE_OPTIONS[score]
    if row.global_score is not None:
        records["总体评分"] = row.global_score
    if row.cdrsb is not None:
        records["CDRSB总分"] = row.cdrsb
    return records


def normalize_number(value: Any) -> float | None:
    text = clean(value)
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def same_record(existing: dict[str, Any], desired: dict[str, Any]) -> bool:
    for field in OPTION_FIELDS:
        if clean(existing.get(field)) != clean(desired.get(field)):
            return False
    for field in NUMERIC_FIELDS:
        if normalize_number(existing.get(field)) != normalize_number(desired.get(field)):
            return False
    return True


def submit(requests: Any, args: argparse.Namespace, row: CdrRow, patient_id: int, existing: dict[str, Any] | None) -> str:
    records = build_records(row, patient_id)
    if existing is not None:
        record_id = existing.get("id")
        if same_record(existing, records):
            return f"SKIPPED: 已存在相同记录 id={record_id}"
        if args.on_existing == "skip":
            return f"CONFLICT_SKIPPED: 已存在不同记录 id={record_id}"
        if args.on_existing == "error":
            raise ImportFailure(f"{row.ptid}/{row.visit_date} 已存在不同记录 id={record_id}")
        if not record_id:
            raise ImportFailure(f"{row.ptid}/{row.visit_date} 既有记录缺少 id")
        api_post(requests, args, "/form/updateData", {"id": int(record_id), "formId": args.form_id, "records": records})
        return f"UPDATED: id={record_id}"
    api_post(requests, args, "/form/insertData", {"formId": args.form_id, "records": records})
    return "INSERTED"


def main() -> int:
    args = parse_args()
    try:
        psycopg2, requests = require_dependencies()
        csv_rows, rejected = load_csv(args.csv)
        patients = query_patients(args, psycopg2)
        if args.patient_number:
            wanted = args.patient_number.strip()
            if wanted not in patients:
                raise ImportFailure(f"项目 {args.project_id} 中找不到 patient_number={wanted}")
            csv_rows = [row for row in csv_rows if row.ptid == wanted]
            rejected = [row for row in rejected if row.ptid == wanted]
            if not csv_rows and not rejected:
                raise ImportFailure(f"CSV 中找不到 PTID={wanted}")

        rejected = [row for row in rejected if row.ptid in patients]
        matched = [row for row in csv_rows if row.ptid in patients]
        outside_project = len(csv_rows) - len(matched)
        reject_duplicate_keys(matched)
        grouped: dict[str, list[CdrRow]] = {}
        for row in matched:
            grouped.setdefault(row.ptid, []).append(row)

        results = list(rejected)
        mode = "commit" if args.commit else "dry-run"
        print(f"CDR {mode}: 匹配 {len(grouped)} 位患者、{len(matched)} 条有效访视")
        for index, ptid in enumerate(sorted(grouped), start=1):
            patient = patients[ptid]
            rows = sorted(grouped[ptid], key=lambda row: (row.visit_date, row.source_row))
            print(f"[{index}/{len(grouped)}] {ptid} -> patient_id={patient.patient_id}, {len(rows)} 条")
            try:
                existing = query_existing(requests, args, patient.patient_id) if args.commit else {}
                for row in rows:
                    status = submit(requests, args, row, patient.patient_id, existing.get(row.visit_date)) if args.commit else "READY"
                    message = "; ".join(row.warnings)
                    results.append(ResultRow(ptid, patient.patient_id, row.visit_date, row.viscode2, status, message, row.warnings))
                    suffix = f" WARNING: {message}" if message else ""
                    print(f"  {row.visit_date} {row.viscode2 or '-'}: {status}{suffix}")
            except ImportFailure as exc:
                message = str(exc)
                print(f"  ERROR: {message}", file=sys.stderr)
                completed = {(item.ptid, item.visit_date) for item in results}
                for row in rows:
                    if (ptid, row.visit_date) not in completed:
                        results.append(ResultRow(ptid, patient.patient_id, row.visit_date, row.viscode2, "FAILED", message))

        counts: dict[str, int] = {}
        warning_count = 0
        for item in results:
            category = item.status.split(":", 1)[0]
            counts[category] = counts.get(category, 0) + 1
            warning_count += bool(item.warnings)
        report = {
            "mode": mode, "csv": str(args.csv), "project_id": args.project_id, "form_id": args.form_id,
            "matched_patients": len(grouped), "matched_valid_visits": len(matched),
            "valid_visits_outside_project": outside_project, "warning_records": warning_count,
            "counts": counts, "results": [asdict(item) for item in results],
        }
        print(json.dumps({k: v for k, v in report.items() if k != "results"}, ensure_ascii=False, indent=2))
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"报告已写入: {args.report}")
        if not args.commit:
            print("DRY-RUN: 未调用 RWE 查询或写入接口；确认后添加 --commit")
        return 2 if counts.get("FAILED", 0) else 0
    except ImportFailure as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("ERROR: 用户取消", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
