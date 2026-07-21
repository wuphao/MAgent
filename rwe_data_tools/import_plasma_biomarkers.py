"""Import UPENN plasma biomarkers into RWE multi-fill form 88.

PostgreSQL is used only for read-only patient lookup. RWE form records are
queried and written through the HTTP API. The default mode is a dry run;
pass --commit to write data.
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


DEFAULT_CSV_PATH = Path(r"C:\Users\admin\Downloads\UPENN_PLASMA_FUJIREBIO_QUANTERIX_21Jul2026.csv")
DEFAULT_PROJECT_ID = 8
DEFAULT_FORM_ID = 88
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

DATE_FIELD = "血液采集日期"
CSV_TO_FORM_FIELDS = {
    "pT217_F": "血浆磷酸化Tau217浓度(pg/mL)",
    "AB42_F": "血浆β淀粉样蛋白42浓度",
    "AB40_F": "血浆β淀粉样蛋白40浓度",
    "AB42_AB40_F": "β淀粉样蛋白42/40比例",
    "pT217_AB42_F": "磷酸化Tau217 / Aβ42 比值",
    "NfL_Q": "神经丝轻链定量值",
    "GFAP_Q": "胶质纤维酸性蛋白定量值",
    "NfL_F": "最终处理后的神经丝轻链浓度",
    "GFAP_F": "最终处理后的胶质纤维酸性蛋白浓度",
}
MISSING_CODES = {-4.0}


class ImportFailure(RuntimeError):
    """Expected, user-facing import failure."""


@dataclass(frozen=True)
class PlasmaRow:
    source_row: int
    ptid: str
    rid: str
    phase: str
    viscode: str
    viscode2: str
    exam_date: str
    values: dict[str, float | None]


@dataclass(frozen=True)
class PatientRef:
    patient_number: str
    patient_id: int


@dataclass
class ResultRow:
    ptid: str
    patient_id: int | None
    exam_date: str
    viscode2: str
    status: str
    message: str = ""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import UPENN plasma biomarkers into RWE form 88.")
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV_PATH)
    parser.add_argument("--project-id", type=int, default=DEFAULT_PROJECT_ID)
    parser.add_argument("--form-id", type=int, default=DEFAULT_FORM_ID)
    parser.add_argument("--patient-number", help="Only process this exact PTID.")
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
        help="Action when the same patient and collection date already exist.",
    )
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--commit", action="store_true", help="Actually write through the RWE API.")
    parser.add_argument("--report", type=Path, help="Optional JSON report path.")
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
        raise ImportFailure(f"CSV 第 {row_number} 行 EXAMDATE 为空")
    for pattern in ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y", "%Y%m%d"):
        try:
            return datetime.strptime(text, pattern).strftime("%Y-%m-%d")
        except ValueError:
            pass
    raise ImportFailure(f"CSV 第 {row_number} 行 EXAMDATE 格式无法识别: {text}")


def parse_measurement(value: Any, column: str, row_number: int) -> float | None:
    text = clean(value)
    if not text:
        return None
    try:
        number = float(text)
    except ValueError as exc:
        raise ImportFailure(f"CSV 第 {row_number} 行 {column} 不是数字: {text}") from exc
    if not math.isfinite(number):
        return None
    if number in MISSING_CODES:
        return None
    if number < 0:
        raise ImportFailure(f"CSV 第 {row_number} 行 {column} 出现未识别的负值: {number}")
    return number


def load_csv(path: Path) -> tuple[list[PlasmaRow], list[ResultRow]]:
    if not path.is_file():
        raise ImportFailure(f"CSV 文件不存在: {path}")
    rows: list[PlasmaRow] = []
    rejected: list[ResultRow] = []
    required_columns = {"PTID", "EXAMDATE", *CSV_TO_FORM_FIELDS}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        columns = {clean(name) for name in (reader.fieldnames or [])}
        missing = sorted(required_columns - columns)
        if missing:
            raise ImportFailure("CSV 缺少列: " + ", ".join(missing))
        for row_number, raw in enumerate(reader, start=2):
            raw = {clean(key): value for key, value in raw.items()}
            ptid = clean(raw.get("PTID"))
            if not ptid:
                rejected.append(ResultRow("", None, "", clean(raw.get("VISCODE2")), "FAILED", f"第 {row_number} 行 PTID 为空"))
                continue
            try:
                exam_date = parse_date(raw.get("EXAMDATE"), row_number)
                values = {
                    csv_name: parse_measurement(raw.get(csv_name), csv_name, row_number)
                    for csv_name in CSV_TO_FORM_FIELDS
                }
            except ImportFailure as exc:
                rejected.append(ResultRow(ptid, None, clean(raw.get("EXAMDATE")), clean(raw.get("VISCODE2")), "FAILED", str(exc)))
                continue
            if not any(value is not None for value in values.values()):
                rejected.append(ResultRow(ptid, None, exam_date, clean(raw.get("VISCODE2")), "EMPTY_VALUES", "所有生物标志物均为空或-4"))
                continue
            rows.append(
                PlasmaRow(
                    source_row=row_number,
                    ptid=ptid,
                    rid=clean(raw.get("RID")),
                    phase=clean(raw.get("PHASE")),
                    viscode=clean(raw.get("VISCODE")),
                    viscode2=clean(raw.get("VISCODE2")),
                    exam_date=exam_date,
                    values=values,
                )
            )
    return rows, rejected


def reject_duplicate_source_keys(rows: list[PlasmaRow]) -> None:
    seen: dict[tuple[str, str], int] = {}
    duplicates: list[str] = []
    for row in rows:
        key = (row.ptid, row.exam_date)
        if key in seen:
            duplicates.append(f"{row.ptid}/{row.exam_date} (CSV 行 {seen[key]} 和 {row.source_row})")
        else:
            seen[key] = row.source_row
    if duplicates:
        raise ImportFailure("CSV 存在重复 PTID + EXAMDATE: " + "; ".join(duplicates[:10]))


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
    token = clean(token)
    if not token:
        raise ImportFailure("API Token 为空")
    return token if token.lower().startswith("bearer ") else f"Bearer {token}"


def api_post(requests: Any, args: argparse.Namespace, path: str, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        response = requests.post(
            f"{args.api_base_url.rstrip('/')}{path}",
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
    if not isinstance(result, dict) or result.get("code") != 0:
        message = result.get("message", result) if isinstance(result, dict) else result
        raise ImportFailure(f"API 业务失败 {path}: {message}")
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
        try:
            exam_date = parse_date(item.get(DATE_FIELD), 0)
        except ImportFailure:
            continue
        if exam_date in existing:
            raise ImportFailure(f"患者 {patient_id} 在 {exam_date} 有多条既有表单记录")
        existing[exam_date] = item
    return existing


def build_records(row: PlasmaRow, patient_id: int) -> dict[str, Any]:
    records: dict[str, Any] = {"patient_id": patient_id, DATE_FIELD: row.exam_date}
    for csv_name, form_name in CSV_TO_FORM_FIELDS.items():
        value = row.values[csv_name]
        if value is not None:
            records[form_name] = value
    return records


def normalized_number(value: Any) -> float | None:
    text = clean(value)
    if not text:
        return None
    try:
        number = float(text)
    except ValueError:
        return None
    return number if math.isfinite(number) and number not in MISSING_CODES else None


def same_values(existing: dict[str, Any], row: PlasmaRow) -> bool:
    return all(
        normalized_number(existing.get(form_name)) == row.values[csv_name]
        for csv_name, form_name in CSV_TO_FORM_FIELDS.items()
    )


def submit_row(
    requests: Any,
    args: argparse.Namespace,
    row: PlasmaRow,
    patient_id: int,
    existing: dict[str, Any] | None,
) -> str:
    records = build_records(row, patient_id)
    if existing is not None:
        record_id = existing.get("id")
        if same_values(existing, row):
            return f"SKIPPED: 已存在相同记录 id={record_id}"
        if args.on_existing == "skip":
            return f"CONFLICT_SKIPPED: 已存在不同结果 id={record_id}"
        if args.on_existing == "error":
            raise ImportFailure(f"{row.ptid}/{row.exam_date} 已存在不同结果 id={record_id}")
        if not record_id:
            raise ImportFailure(f"{row.ptid}/{row.exam_date} 既有记录缺少 id")
        api_post(requests, args, "/form/updateData", {"id": int(record_id), "formId": args.form_id, "records": records})
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
        grouped: dict[str, list[PlasmaRow]] = {}
        for row in matched_rows:
            grouped.setdefault(row.ptid, []).append(row)

        mode = "commit" if args.commit else "dry-run"
        print(f"Plasma biomarkers {mode}: 匹配 {len(grouped)} 位患者、{len(matched_rows)} 条有效记录。")
        for index, ptid in enumerate(sorted(grouped), start=1):
            patient = patients[ptid]
            patient_rows = sorted(grouped[ptid], key=lambda row: (row.exam_date, row.source_row))
            print(f"[{index}/{len(grouped)}] {ptid} -> patient_id={patient.patient_id}, {len(patient_rows)} 条")
            try:
                existing_by_date = query_existing_for_patient(requests, args, patient.patient_id) if args.commit else {}
                for row in patient_rows:
                    status = "READY" if not args.commit else submit_row(
                        requests, args, row, patient.patient_id, existing_by_date.get(row.exam_date)
                    )
                    results.append(ResultRow(ptid, patient.patient_id, row.exam_date, row.viscode2, status))
                    print(f"  {row.exam_date} {row.viscode2 or '-'}: {status}")
            except ImportFailure as exc:
                message = str(exc)
                print(f"  ERROR: {message}", file=sys.stderr)
                for row in patient_rows:
                    if not any(item.ptid == ptid and item.exam_date == row.exam_date for item in results):
                        results.append(ResultRow(ptid, patient.patient_id, row.exam_date, row.viscode2, "FAILED", message))

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
            "matched_valid_records": len(matched_rows),
            "valid_records_outside_project": len(unmatched_rows),
            "missing_value_codes": sorted(MISSING_CODES),
            "counts": counts,
            "results": [asdict(item) for item in results],
        }
        print(json.dumps({key: value for key, value in report.items() if key != "results"}, ensure_ascii=False, indent=2))
        if args.report:
            write_report(args.report, report)
            print(f"报告已写入: {args.report.resolve()}")
        if not args.commit:
            print("DRY-RUN: 未调用 RWE 查询或写入接口；确认后添加 --commit。")
        return 2 if counts.get("FAILED", 0) else 0
    except ImportFailure as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("ERROR: 用户取消。", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
