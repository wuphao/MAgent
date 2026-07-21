"""Import APOE genotype results into RWE form 89.

The source genotype values are normalized from forms such as 3/4 or 3月4日
to explicit allele notation such as ε3/ε4. Dry-run is the default.
"""

from __future__ import annotations

import argparse
import csv
import json
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
    query_project_patients,
    require_dependencies,
    write_report,
)


DEFAULT_CSV_PATH = Path(r"C:\Users\admin\Downloads\APOERES_21Jul2026.csv")
DEFAULT_FORM_ID = 89
DATE_FIELD = "APOE检测日期"
GENOTYPE_FIELD = "APOE基因型"


@dataclass(frozen=True)
class ApoeRow:
    source_row: int
    ptid: str
    rid: str
    test_date: str
    genotype: str
    source_genotype: str


@dataclass
class ResultRow:
    ptid: str
    patient_id: int | None
    test_date: str
    genotype: str
    status: str
    message: str = ""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import APOE genotype results into RWE form 89.")
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
    parser.add_argument("--on-existing", choices=("skip", "update", "error"), default="skip")
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--commit", action="store_true")
    parser.add_argument("--report", type=Path)
    return parser.parse_args()


def parse_optional_date(value: Any, row_number: int) -> str:
    text = clean(value)
    if not text:
        return ""
    for pattern in ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y", "%Y%m%d"):
        try:
            return datetime.strptime(text, pattern).strftime("%Y-%m-%d")
        except ValueError:
            pass
    raise ImportFailure(f"CSV 第 {row_number} 行 APTESTDT 格式无法识别: {text}")


def normalize_genotype(value: Any, row_number: int) -> str:
    source = clean(value)
    if not source:
        raise ImportFailure(f"CSV 第 {row_number} 行 GENOTYPE 为空")
    normalized = source.lower().replace("apoe", "").replace("ε", "").replace("e", "").strip()
    patterns = (
        r"^([234])\s*/\s*([234])$",
        r"^([234])\s*月\s*([234])\s*日?$",
        r"^([234])\s*[-_]\s*([234])$",
    )
    alleles: tuple[int, int] | None = None
    for pattern in patterns:
        match = re.fullmatch(pattern, normalized)
        if match:
            alleles = (int(match.group(1)), int(match.group(2)))
            break
    if alleles is None:
        # Handles accidental spreadsheet date serialization such as 1900-03-04.
        date_match = re.fullmatch(r"\d{4}[-/]0?([234])[-/]0?([234])", normalized)
        if date_match:
            alleles = (int(date_match.group(1)), int(date_match.group(2)))
    if alleles is None:
        raise ImportFailure(f"CSV 第 {row_number} 行无法识别 GENOTYPE: {source}")
    first, second = sorted(alleles)
    return f"ε{first}/ε{second}"


def load_csv(path: Path) -> tuple[list[ApoeRow], list[ResultRow]]:
    if not path.is_file():
        raise ImportFailure(f"CSV 文件不存在: {path}")
    rows: list[ApoeRow] = []
    rejected: list[ResultRow] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        columns = {clean(name) for name in (reader.fieldnames or [])}
        missing = sorted({"PTID", "GENOTYPE", "APTESTDT"} - columns)
        if missing:
            raise ImportFailure("CSV 缺少列: " + ", ".join(missing))
        seen: set[str] = set()
        for row_number, source in enumerate(reader, start=2):
            raw = {clean(key): value for key, value in source.items()}
            ptid = clean(raw.get("PTID"))
            if not ptid:
                rejected.append(ResultRow("", None, "", "", "FAILED", f"CSV 第 {row_number} 行 PTID 为空"))
                continue
            if ptid in seen:
                raise ImportFailure(f"CSV 中 PTID={ptid} 出现多条记录")
            seen.add(ptid)
            try:
                test_date = parse_optional_date(raw.get("APTESTDT"), row_number)
                genotype = normalize_genotype(raw.get("GENOTYPE"), row_number)
            except ImportFailure as exc:
                rejected.append(ResultRow(ptid, None, clean(raw.get("APTESTDT")), "", "FAILED", str(exc)))
                continue
            rows.append(ApoeRow(row_number, ptid, clean(raw.get("RID")), test_date, genotype, clean(raw.get("GENOTYPE"))))
    return rows, rejected


def query_existing_for_patient(requests: Any, args: argparse.Namespace, patient_id: int) -> list[dict[str, Any]]:
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
    return list(((response.get("data") or {}).get("list") or []))


def normalized_existing_genotype(value: Any) -> str:
    text = clean(value)
    if not text:
        return ""
    try:
        return normalize_genotype(text, 0)
    except ImportFailure:
        return text


def same_record(existing: dict[str, Any], row: ApoeRow) -> bool:
    existing_date = parse_optional_date(existing.get(DATE_FIELD), 0)
    return existing_date == row.test_date and normalized_existing_genotype(existing.get(GENOTYPE_FIELD)) == row.genotype


def build_records(row: ApoeRow, patient_id: int) -> dict[str, Any]:
    records: dict[str, Any] = {"patient_id": patient_id, GENOTYPE_FIELD: row.genotype}
    if row.test_date:
        records[DATE_FIELD] = row.test_date
    return records


def submit_row(requests: Any, args: argparse.Namespace, row: ApoeRow, patient_id: int, existing: list[dict[str, Any]]) -> str:
    exact = next((item for item in existing if same_record(item, row)), None)
    if exact is not None:
        return f"SKIPPED: 已存在相同记录 id={exact.get('id')}"
    if existing:
        if args.on_existing == "skip":
            return f"CONFLICT_SKIPPED: 已存在不同APOE记录，共{len(existing)}条"
        if args.on_existing == "error":
            raise ImportFailure(f"{row.ptid} 已存在不同APOE记录")
        if len(existing) != 1 or not existing[0].get("id"):
            raise ImportFailure(f"{row.ptid} 有 {len(existing)} 条既有记录，无法安全更新")
        record_id = int(existing[0]["id"])
        api_post(requests, args, "/form/updateData", {"id": record_id, "formId": args.form_id, "records": build_records(row, patient_id)})
        return f"UPDATED: id={record_id}"
    api_post(requests, args, "/form/insertData", {"formId": args.form_id, "records": build_records(row, patient_id)})
    return "INSERTED"


def main() -> int:
    args = parse_args()
    try:
        psycopg2, requests = require_dependencies()
        csv_rows, preliminary = load_csv(args.csv)
        patients = query_project_patients(args, psycopg2)
        if args.patient_number:
            wanted = args.patient_number.strip()
            csv_rows = [row for row in csv_rows if row.ptid == wanted]
            preliminary = [row for row in preliminary if row.ptid == wanted]
            if wanted not in patients:
                raise ImportFailure(f"项目 {args.project_id} 中找不到 patient_number={wanted}")
            if not csv_rows and not preliminary:
                raise ImportFailure(f"CSV 中找不到 PTID={wanted}")

        matched = [row for row in csv_rows if row.ptid in patients]
        unmatched = [row for row in csv_rows if row.ptid not in patients]
        results = [row for row in preliminary if row.ptid in patients]
        mode = "commit" if args.commit else "dry-run"
        print(f"APOE {mode}: 匹配 {len(matched)} 位患者、{len(matched)} 条有效记录。")
        for index, row in enumerate(sorted(matched, key=lambda item: item.ptid), start=1):
            patient = patients[row.ptid]
            try:
                existing = query_existing_for_patient(requests, args, patient.patient_id) if args.commit else []
                status = "READY" if not args.commit else submit_row(requests, args, row, patient.patient_id, existing)
                results.append(ResultRow(row.ptid, patient.patient_id, row.test_date, row.genotype, status))
                print(f"[{index}/{len(matched)}] {row.ptid} -> patient_id={patient.patient_id}: {row.genotype}, {row.test_date or '无日期'}: {status}")
            except ImportFailure as exc:
                results.append(ResultRow(row.ptid, patient.patient_id, row.test_date, row.genotype, "FAILED", str(exc)))
                print(f"[{index}/{len(matched)}] {row.ptid}: ERROR: {exc}", file=sys.stderr)

        counts: dict[str, int] = {}
        for item in results:
            category = item.status.split(":", 1)[0]
            counts[category] = counts.get(category, 0) + 1
        report = {
            "mode": mode,
            "csv": str(args.csv),
            "project_id": args.project_id,
            "form_id": args.form_id,
            "matched_patients": len(matched),
            "valid_records_outside_project": len(unmatched),
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
