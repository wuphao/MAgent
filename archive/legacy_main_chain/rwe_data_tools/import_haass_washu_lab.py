"""Import ADNI Haass/WashU CSF biomarkers into RWE multi-fill form 90.

The source contains RID rather than PTID. Patients are matched by the numeric
suffix of patient_project.patient_number. Dry-run is the default; use
--commit to write records through the RWE API.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from import_plasma_biomarkers import (
    DEFAULT_API_BASE_URL,
    DEFAULT_DB_HOST,
    DEFAULT_DB_NAME,
    DEFAULT_DB_PASSWORD,
    DEFAULT_DB_PORT,
    DEFAULT_DB_USER,
    DEFAULT_PROJECT_ID,
    DEFAULT_RWE_TOKEN,
    ImportFailure,
    api_post,
    clean,
    require_dependencies,
    write_report,
)


DEFAULT_CSV_PATH = Path(r"C:\Users\admin\Downloads\ADNI_HAASS_WASHU_LAB_21Jul2026.csv")
DEFAULT_FORM_ID = 90
DATE_FIELD = "检查/采样日期"
CSV_TO_FORM_FIELDS = {
    "WU_STREM2": "sTREM2 原始浓度",
    "WU_STREM2_CV": "sTREM2 变异系数",
    "WU_STREM2CORRECTED": "sTREM2 校正值",
    "MSD_STREM2": "Haass/MSD sTREM2 原始浓度",
    "MSD_STREM2_CV": "Haass/MSD sTREM2 变异系数",
    "MSD_STREM2CORRECTED": "Haass/MSD sTREM2 校正值",
    "MSD_PGRN": "Haass/MSD PGRN 原始浓度",
    "MSD_PGRN_CV": "Haass/MSD PGRN 变异系数",
    "MSD_PGRNCORRECTED": "Haass/MSD PGRN 校正值",
}
OUTLIER_COLUMN = "TREM2OUTLIER"
OUTLIER_FORM_FIELD = "TREM2 异常值标记/说明"
MISSING_NUMERIC_CODES = {-4.0}


@dataclass(frozen=True)
class WashuRow:
    source_row: int
    rid: int
    viscode: str
    viscode2: str
    exam_date: str
    values: dict[str, float | None]
    outlier_text: str


@dataclass(frozen=True)
class PatientRef:
    patient_number: str
    patient_id: int
    rid: int


@dataclass
class ResultRow:
    rid: int
    patient_number: str
    patient_id: int | None
    exam_date: str
    viscode2: str
    source_row: int
    status: str
    message: str = ""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import ADNI Haass/WashU CSF biomarkers into RWE form 90.")
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV_PATH)
    parser.add_argument("--project-id", type=int, default=DEFAULT_PROJECT_ID)
    parser.add_argument("--form-id", type=int, default=DEFAULT_FORM_ID)
    parser.add_argument("--patient-number", help="Only process this exact patient number, e.g. 011_S_0031.")
    parser.add_argument("--rid", type=int, help="Only process this RID.")
    parser.add_argument("--api-base-url", default=DEFAULT_API_BASE_URL)
    parser.add_argument("--token", default=DEFAULT_RWE_TOKEN)
    parser.add_argument("--db-host", default=DEFAULT_DB_HOST)
    parser.add_argument("--db-port", type=int, default=DEFAULT_DB_PORT)
    parser.add_argument("--db-name", default=DEFAULT_DB_NAME)
    parser.add_argument("--db-user", default=DEFAULT_DB_USER)
    parser.add_argument("--db-password", default=DEFAULT_DB_PASSWORD)
    parser.add_argument(
        "--on-existing",
        choices=("insert-distinct", "update", "error"),
        default="insert-distinct",
        help="Exact duplicates are always skipped; distinct same-date rows are inserted by default.",
    )
    parser.add_argument(
        "--include-outlier-text",
        action="store_true",
        help="Submit TREM2OUTLIER text only after changing form field 573 to text type.",
    )
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--commit", action="store_true")
    parser.add_argument("--report", type=Path)
    return parser.parse_args()


def parse_date(value: Any, row_number: int, *, allow_empty: bool = False) -> str:
    text = clean(value)
    if not text:
        if allow_empty:
            return ""
        raise ImportFailure(f"CSV 第 {row_number} 行 EXAMDATE 为空")
    for pattern in ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y", "%Y%m%d"):
        try:
            return datetime.strptime(text, pattern).strftime("%Y-%m-%d")
        except ValueError:
            pass
    raise ImportFailure(f"CSV 第 {row_number} 行 EXAMDATE 格式无法识别: {text}")


def parse_rid(value: Any, row_number: int) -> int:
    text = clean(value)
    try:
        rid = int(text)
    except ValueError as exc:
        raise ImportFailure(f"CSV 第 {row_number} 行 RID 不是整数: {text}") from exc
    if rid <= 0:
        raise ImportFailure(f"CSV 第 {row_number} 行 RID 无效: {rid}")
    return rid


def parse_measurement(value: Any, column: str, row_number: int) -> float | None:
    text = clean(value)
    if not text:
        return None
    try:
        number = float(text)
    except ValueError as exc:
        raise ImportFailure(f"CSV 第 {row_number} 行 {column} 不是数字: {text}") from exc
    if not math.isfinite(number) or number in MISSING_NUMERIC_CODES:
        return None
    if number < 0:
        raise ImportFailure(f"CSV 第 {row_number} 行 {column} 出现未识别的负值: {number}")
    return number


def load_csv(path: Path) -> tuple[list[WashuRow], list[ResultRow]]:
    if not path.is_file():
        raise ImportFailure(f"CSV 文件不存在: {path}")
    rows: list[WashuRow] = []
    rejected: list[ResultRow] = []
    required = {"RID", "EXAMDATE", OUTLIER_COLUMN, *CSV_TO_FORM_FIELDS}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        columns = {clean(name) for name in (reader.fieldnames or [])}
        missing = sorted(required - columns)
        if missing:
            raise ImportFailure("CSV 缺少列: " + ", ".join(missing))
        for row_number, source in enumerate(reader, start=2):
            raw = {clean(key): value for key, value in source.items()}
            rid = 0
            try:
                rid = parse_rid(raw.get("RID"), row_number)
                exam_date = parse_date(raw.get("EXAMDATE"), row_number, allow_empty=True)
                values = {
                    csv_name: parse_measurement(raw.get(csv_name), csv_name, row_number)
                    for csv_name in CSV_TO_FORM_FIELDS
                }
            except ImportFailure as exc:
                rejected.append(ResultRow(rid, "", None, clean(raw.get("EXAMDATE")), clean(raw.get("VISCODE2")), row_number, "FAILED", str(exc)))
                continue
            outlier_text = clean(raw.get(OUTLIER_COLUMN))
            if not any(value is not None for value in values.values()) and not outlier_text:
                rejected.append(ResultRow(rid, "", None, exam_date, clean(raw.get("VISCODE2")), row_number, "EMPTY_VALUES", "所有指标均为空"))
                continue
            rows.append(
                WashuRow(
                    source_row=row_number,
                    rid=rid,
                    viscode=clean(raw.get("VISCODE")),
                    viscode2=clean(raw.get("VISCODE2")),
                    exam_date=exam_date,
                    values=values,
                    outlier_text=outlier_text,
                )
            )
    return rows, rejected


def patient_number_rid(patient_number: str) -> int | None:
    match = re.search(r"(?:^|_)(\d+)$", patient_number.strip())
    return int(match.group(1)) if match else None


def query_project_patients_by_rid(args: argparse.Namespace, psycopg2: Any) -> dict[int, PatientRef]:
    sql = """
        SELECT TRIM(pp.patient_number), pp.patient_id
        FROM patient_project pp
        JOIN patient p ON p.id = pp.patient_id
        WHERE pp.project_id = %s AND pp.is_delete = 0 AND p.is_delete = 0
          AND pp.patient_number IS NOT NULL AND TRIM(pp.patient_number) <> ''
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
    result: dict[int, PatientRef] = {}
    for number, patient_id in records:
        rid = patient_number_rid(number)
        if rid is None:
            continue
        if rid in result and result[rid].patient_number != number:
            raise ImportFailure(f"项目 {args.project_id} 中 RID={rid} 对应多个患者编号")
        result[rid] = PatientRef(number, int(patient_id), rid)
    return result


def query_existing_for_patient(requests: Any, args: argparse.Namespace, patient_id: int) -> dict[str, list[dict[str, Any]]]:
    response = api_post(
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
    by_date: dict[str, list[dict[str, Any]]] = {}
    for item in ((response.get("data") or {}).get("list") or []):
        try:
            date = parse_date(item.get(DATE_FIELD), 0, allow_empty=True)
        except ImportFailure:
            continue
        by_date.setdefault(date, []).append(item)
    return by_date


def build_records(row: WashuRow, patient_id: int, include_outlier_text: bool) -> dict[str, Any]:
    records: dict[str, Any] = {"patient_id": patient_id}
    if row.exam_date:
        records[DATE_FIELD] = row.exam_date
    for csv_name, form_name in CSV_TO_FORM_FIELDS.items():
        value = row.values[csv_name]
        if value is not None:
            records[form_name] = value
    if include_outlier_text and row.outlier_text:
        records[OUTLIER_FORM_FIELD] = row.outlier_text
    return records


def normalized_number(value: Any) -> float | None:
    text = clean(value)
    if not text:
        return None
    try:
        number = float(text)
    except ValueError:
        return None
    return number if math.isfinite(number) and number not in MISSING_NUMERIC_CODES else None


def same_values(existing: dict[str, Any], row: WashuRow, include_outlier_text: bool) -> bool:
    numeric_equal = all(
        normalized_number(existing.get(form_name)) == row.values[csv_name]
        for csv_name, form_name in CSV_TO_FORM_FIELDS.items()
    )
    if not numeric_equal:
        return False
    return not include_outlier_text or clean(existing.get(OUTLIER_FORM_FIELD)) == row.outlier_text


def submit_row(
    requests: Any,
    args: argparse.Namespace,
    row: WashuRow,
    patient_id: int,
    candidates: list[dict[str, Any]],
) -> tuple[str, dict[str, Any] | None]:
    records = build_records(row, patient_id, args.include_outlier_text)
    exact = next((item for item in candidates if same_values(item, row, args.include_outlier_text)), None)
    if exact is not None:
        return f"SKIPPED: 已存在相同记录 id={exact.get('id')}", None
    if candidates and args.on_existing == "error":
        raise ImportFailure(f"RID={row.rid}/{row.exam_date} 已存在不同记录")
    if candidates and args.on_existing == "update":
        if len(candidates) != 1:
            raise ImportFailure(f"RID={row.rid}/{row.exam_date} 有 {len(candidates)} 条既有记录，无法安全更新")
        record_id = candidates[0].get("id")
        if not record_id:
            raise ImportFailure(f"RID={row.rid}/{row.exam_date} 既有记录缺少 id")
        api_post(requests, args, "/form/updateData", {"id": int(record_id), "formId": args.form_id, "records": records})
        records["id"] = record_id
        return f"UPDATED: id={record_id}", records
    api_post(requests, args, "/form/insertData", {"formId": args.form_id, "records": records})
    return "INSERTED", records


def main() -> int:
    args = parse_args()
    try:
        psycopg2, requests = require_dependencies()
        csv_rows, preliminary = load_csv(args.csv)
        patients = query_project_patients_by_rid(args, psycopg2)
        selected_rid = args.rid
        if args.patient_number:
            wanted = args.patient_number.strip()
            matches = [patient for patient in patients.values() if patient.patient_number == wanted]
            if not matches:
                raise ImportFailure(f"项目 {args.project_id} 中找不到 patient_number={wanted}")
            if selected_rid is not None and selected_rid != matches[0].rid:
                raise ImportFailure("--patient-number 与 --rid 不一致")
            selected_rid = matches[0].rid
        if selected_rid is not None:
            csv_rows = [row for row in csv_rows if row.rid == selected_rid]
            preliminary = [row for row in preliminary if row.rid in (0, selected_rid)]
            if selected_rid not in patients:
                raise ImportFailure(f"项目 {args.project_id} 中找不到 RID={selected_rid}")
            if not csv_rows and not preliminary:
                raise ImportFailure(f"CSV 中找不到 RID={selected_rid}")

        matched = [row for row in csv_rows if row.rid in patients]
        unmatched = [row for row in csv_rows if row.rid not in patients]
        results = [row for row in preliminary if row.rid == 0 or row.rid in patients]
        grouped: dict[int, list[WashuRow]] = {}
        for row in matched:
            grouped.setdefault(row.rid, []).append(row)

        mode = "commit" if args.commit else "dry-run"
        outlier_count = sum(bool(row.outlier_text) for row in matched)
        print(f"Haass/WashU {mode}: 匹配 {len(grouped)} 位患者、{len(matched)} 条有效记录。")
        if outlier_count and not args.include_outlier_text:
            print(f"提示: {outlier_count} 条 TREM2OUTLIER 文本未提交；字段 573 当前为小数类型。")
        for index, rid in enumerate(sorted(grouped), start=1):
            patient = patients[rid]
            rows = sorted(grouped[rid], key=lambda item: (item.exam_date, item.source_row))
            print(f"[{index}/{len(grouped)}] RID={rid} -> {patient.patient_number}, patient_id={patient.patient_id}, {len(rows)} 条")
            try:
                existing = query_existing_for_patient(requests, args, patient.patient_id) if args.commit else {}
                for row in rows:
                    if args.commit:
                        status, inserted = submit_row(requests, args, row, patient.patient_id, existing.get(row.exam_date, []))
                        if inserted is not None:
                            existing.setdefault(row.exam_date, []).append(inserted)
                    else:
                        status = "READY"
                    results.append(ResultRow(rid, patient.patient_number, patient.patient_id, row.exam_date, row.viscode2, row.source_row, status))
                    print(f"  CSV#{row.source_row} {row.exam_date} {row.viscode2 or '-'}: {status}")
            except ImportFailure as exc:
                message = str(exc)
                print(f"  ERROR: {message}", file=sys.stderr)
                for row in rows:
                    if not any(item.rid == rid and item.source_row == row.source_row for item in results):
                        results.append(ResultRow(rid, patient.patient_number, patient.patient_id, row.exam_date, row.viscode2, row.source_row, "FAILED", message))

        counts: dict[str, int] = {}
        for item in results:
            category = item.status.split(":", 1)[0]
            counts[category] = counts.get(category, 0) + 1
        report = {
            "mode": mode,
            "csv": str(args.csv),
            "project_id": args.project_id,
            "form_id": args.form_id,
            "matched_patients": len(grouped),
            "matched_valid_records": len(matched),
            "valid_records_outside_project": len(unmatched),
            "outlier_text_records": outlier_count,
            "outlier_text_submitted": bool(args.include_outlier_text),
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
