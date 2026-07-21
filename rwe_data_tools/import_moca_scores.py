#!/usr/bin/env python3
"""Import longitudinal MoCA detail records into RWE form 55."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_CSV = Path(r"C:\Users\admin\Downloads\MOCA_22Jun2026.csv")
DEFAULT_API_BASE_URL = "http://localhost:8080"
DEFAULT_DB_PASSWORD = "12345678"
DEFAULT_TOKEN = (
    "Bearer "
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJjbGFpbXMiOnsicm9sZSI6ImRvY3RvciIsInBob25lIjoiMTMwMjAzOTczNjYiLCJuYW1lIjoid3BoIiwiaWQiOjJ9LCJleHAiOjE3ODQ5NjM2MjB9."
    "N-I8dEEc0gKVAm6_Lsz8tmU5Pb90wvyJzpKZKVNJxqc"
)

ZERO_ONE_FIELDS = {
    "CLOCKCON": "时钟轮廓是否正确", "CLOCKNO": "评估时钟数字", "CLOCKHAN": "评估指针",
    "LION": "看图说出狮子名称", "RHINO": "看图说出犀牛名称", "CAMEL": "看图说出骆驼名称",
    "ABSTRAN": "火车和自行车有什么共同点", "ABSMEAS": "手表和尺子有什么共同点",
}
CORRECT_FIELDS = {
    "TRAILS": "连线测试",
    "SERIAL1": "第1次减7是否正确", "SERIAL2": "第2次减7是否正确",
    "SERIAL3": "第3次减7是否正确", "SERIAL4": "第4次减7是否正确",
    "SERIAL5": "第5次减7是否正确",
    "DATE": "日期是否回答正确", "MONTH": "月份是否正确", "YEAR": "年份是否正确",
    "DAY": "星期几是否正确", "PLACE": "当前地点是否正确", "CITY": "当前城市是否正确",
}
ROUND1_FIELDS = {
    "IMMT1W1": "第一轮正确复述face", "IMMT1W2": "第一轮正确复述velvet",
    "IMMT1W3": "第一轮正确复述church", "IMMT1W4": "第一轮正确复述daisy",
    "IMMT1W5": "第一轮正确复述red",
}
ROUND2_FIELDS = {
    "IMMT2W1": "第二轮正确复述face", "IMMT2W2": "第二轮正确复述velvet",
    "IMMT2W3": "第二轮正确复述church", "IMMT2W4": "第二轮正确复述daisy",
    "IMMT2W5": "第二轮正确复述red",
}
DELAYED_FIELDS = {
    "DELW1": "无提示回想起face", "DELW2": "无提示回想起velvet",
    "DELW3": "无提示回想起church", "DELW4": "无提示回想起daisy",
    "DELW5": "无提示回想起red",
}
ALL_SOURCES = {
    "TRAILS", "CUBE", *ZERO_ONE_FIELDS, *CORRECT_FIELDS, *ROUND1_FIELDS, *ROUND2_FIELDS,
    "DIGFOR", "DIGBACK", "REPEAT1", "REPEAT2", "FFLUENCY", *DELAYED_FIELDS, "MOCA",
}


class ImportFailure(RuntimeError):
    pass


@dataclass(frozen=True)
class MocaRow:
    source_row: int
    ptid: str
    viscode2: str
    visit_date: str
    values: dict[str, Any]


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
    parser = argparse.ArgumentParser(description="Import MoCA records into RWE form 55.")
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--project-id", type=int, default=8)
    parser.add_argument("--form-id", type=int, default=55)
    parser.add_argument("--patient-number")
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


def dependencies() -> tuple[Any, Any]:
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
        raise ImportFailure("缺少依赖，请安装: " + " ".join(missing))
    return psycopg2, requests


def clean(value: Any) -> str:
    return "" if value is None else str(value).strip().strip("\ufeff")


def parse_date(value: Any, row_number: int) -> str:
    text = clean(value)
    if not text:
        raise ImportFailure(f"第 {row_number} 行 VISDATE 为空")
    for pattern in ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y", "%Y%m%d"):
        try:
            return datetime.strptime(text, pattern).strftime("%Y-%m-%d")
        except ValueError:
            pass
    raise ImportFailure(f"第 {row_number} 行 VISDATE 无法识别: {text}")


def binary(value: Any, label: str, row_number: int, positive: str, negative: str) -> str | None:
    text = clean(value)
    if not text or text in {"-1", "-1.0"}:
        return None
    if text in {"1", "1.0"}:
        return positive
    if text in {"0", "0.0"}:
        return negative
    raise ImportFailure(f"第 {row_number} 行 {label} 不是 0/1/空: {text}")


def integer(value: Any, label: str, row_number: int, lower: int, upper: int) -> int | None:
    text = clean(value)
    if not text or text in {"-1", "-1.0"}:
        return None
    try:
        number = float(text)
    except ValueError as exc:
        raise ImportFailure(f"第 {row_number} 行 {label} 不是数字: {text}") from exc
    if not number.is_integer() or not lower <= number <= upper:
        raise ImportFailure(f"第 {row_number} 行 {label} 超出整数范围 {lower}～{upper}: {text}")
    return int(number)


def delayed_option(value: Any, label: str, row_number: int) -> str | None:
    text = clean(value)
    if not text or text in {"-1", "-1.0"}:
        return None
    try:
        code = int(float(text))
    except ValueError as exc:
        raise ImportFailure(f"第 {row_number} 行 {label} 不是 0～3: {text}") from exc
    if code not in {0, 1, 2, 3}:
        raise ImportFailure(f"第 {row_number} 行 {label} 不在 0～3: {code}")
    return "无提示正确回忆" if code == 3 else "没有无提示回忆出来"


def load_csv(path: Path) -> tuple[list[MocaRow], list[ResultRow]]:
    if not path.is_file():
        raise ImportFailure(f"CSV 不存在: {path}")
    required = {"PTID", "VISDATE", *ALL_SOURCES}
    rows: list[MocaRow] = []
    rejected: list[ResultRow] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = sorted(required - set(reader.fieldnames or []))
        if missing:
            raise ImportFailure("CSV 缺少列: " + ", ".join(missing))
        for row_number, raw in enumerate(reader, start=2):
            ptid, viscode2 = clean(raw.get("PTID")), clean(raw.get("VISCODE2"))
            if not ptid:
                rejected.append(ResultRow("", None, "", viscode2, "FAILED", f"第 {row_number} 行 PTID 为空"))
                continue
            try:
                visit_date = parse_date(raw.get("VISDATE"), row_number)
                values: dict[str, Any] = {}
                value = binary(raw.get("TRAILS"), "TRAILS", row_number, "正确", "错误")
                if value is not None: values["连线测试"] = value
                value = binary(raw.get("CUBE"), "CUBE", row_number, "临摹正确", "不正确")
                if value is not None: values["临摹立方体"] = value
                for source, target in ZERO_ONE_FIELDS.items():
                    value = binary(raw.get(source), source, row_number, "1", "0")
                    if value is not None: values[target] = value
                for source, target in CORRECT_FIELDS.items():
                    value = binary(raw.get(source), source, row_number, "正确", "错误")
                    if value is not None: values[target] = value
                for source, target in ROUND1_FIELDS.items():
                    value = binary(raw.get(source), source, row_number, "第一轮正确复述", "没有正确复述")
                    if value is not None: values[target] = value
                for source, target in ROUND2_FIELDS.items():
                    value = binary(raw.get(source), source, row_number, "第二轮正确复述", "没有正确复述")
                    if value is not None: values[target] = value
                for source, target in {"DIGFOR": "顺背数字", "DIGBACK": "倒背数字"}.items():
                    value = binary(raw.get(source), source, row_number, "没有错误", "一个错误")
                    if value is not None: values[target] = value
                for source, target in {"REPEAT1": "第一条句子是否完整重复正确", "REPEAT2": "第二条句子是否完整重复正确"}.items():
                    value = binary(raw.get(source), source, row_number, "完整正确", "存在遗漏、替换或错误")
                    if value is not None: values[target] = value
                fluency = integer(raw.get("FFLUENCY"), "FFLUENCY", row_number, 0, 100)
                if fluency is not None: values["字母流畅性任务"] = "1" if fluency >= 11 else "0"
                for source, target in DELAYED_FIELDS.items():
                    value = delayed_option(raw.get(source), source, row_number)
                    if value is not None: values[target] = value
                total = integer(raw.get("MOCA"), "MOCA", row_number, 0, 30)
                if total is not None: values["MoCA 汇总得分"] = total
            except ImportFailure as exc:
                rejected.append(ResultRow(ptid, None, clean(raw.get("VISDATE")), viscode2, "FAILED", str(exc)))
                continue
            if not values:
                rejected.append(ResultRow(ptid, None, visit_date, viscode2, "EMPTY_SCORES", "所有保留字段均为空"))
                continue
            rows.append(MocaRow(row_number, ptid, viscode2, visit_date, values))
    return rows, rejected


def reject_duplicates(rows: list[MocaRow]) -> None:
    seen: dict[tuple[str, str], int] = {}
    duplicates: list[str] = []
    for row in rows:
        key = (row.ptid, row.visit_date)
        if key in seen: duplicates.append(f"{row.ptid}/{row.visit_date} (行 {seen[key]}、{row.source_row})")
        else: seen[key] = row.source_row
    if duplicates: raise ImportFailure("本次数据存在重复 PTID + VISDATE: " + "; ".join(duplicates[:10]))


def query_patients(args: argparse.Namespace, psycopg2: Any) -> dict[str, PatientRef]:
    connection = psycopg2.connect(host=args.db_host, port=args.db_port, dbname=args.db_name, user=args.db_user, password=args.db_password, connect_timeout=10)
    try:
        connection.set_session(readonly=True, autocommit=True)
        with connection.cursor() as cursor:
            cursor.execute("""SELECT TRIM(pp.patient_number),pp.patient_id FROM patient_project pp JOIN patient p ON p.id=pp.patient_id
                WHERE pp.project_id=%s AND pp.is_delete=0 AND p.is_delete=0 AND pp.patient_number IS NOT NULL AND TRIM(pp.patient_number)<>''""", (args.project_id,))
            records = cursor.fetchall()
    finally: connection.close()
    return {number: PatientRef(number, int(patient_id)) for number, patient_id in records}


def api_post(requests: Any, args: argparse.Namespace, path: str, payload: dict[str, Any]) -> dict[str, Any]:
    token = clean(args.token)
    authorization = token if token.lower().startswith("bearer ") else f"Bearer {token}"
    try:
        response = requests.post(f"{args.api_base_url.rstrip('/')}{path}", json=payload, headers={"Authorization": authorization, "Content-Type": "application/json"}, timeout=args.timeout)
        response.raise_for_status(); result = response.json()
    except requests.RequestException as exc: raise ImportFailure(f"API 请求失败 {path}: {exc}") from exc
    except ValueError as exc: raise ImportFailure(f"API 返回非 JSON: {path}") from exc
    if not isinstance(result, dict) or result.get("code") != 0:
        raise ImportFailure(f"API 业务失败 {path}: {result.get('message', result) if isinstance(result, dict) else result}")
    return result


def query_existing(requests: Any, args: argparse.Namespace, patient_id: int) -> dict[str, dict[str, Any]]:
    result = api_post(requests, args, "/form/queryData", {"formId": args.form_id, "page": 0, "pageSize": 0, "criteria": [{"enName": "patient_id", "inputValue": patient_id, "isFuzzy": False}]})
    existing: dict[str, dict[str, Any]] = {}
    for item in ((result.get("data") or {}).get("list") or []):
        try: date = parse_date(item.get("访视日期"), 0)
        except ImportFailure: continue
        if date in existing: raise ImportFailure(f"患者 {patient_id} 在 {date} 有多条既有 MoCA 记录")
        existing[date] = item
    return existing


def records_for(row: MocaRow, patient_id: int) -> dict[str, Any]:
    return {"patient_id": patient_id, "访视日期": row.visit_date, **row.values}


def same_record(existing: dict[str, Any], desired: dict[str, Any]) -> bool:
    for field, value in desired.items():
        if field in {"patient_id", "访视日期"}: continue
        old = existing.get(field)
        if isinstance(value, int):
            try:
                if int(float(str(old))) != value: return False
            except (TypeError, ValueError): return False
        elif clean(old) != clean(value): return False
    return True


def submit(requests: Any, args: argparse.Namespace, row: MocaRow, patient_id: int, existing: dict[str, Any] | None) -> str:
    records = records_for(row, patient_id)
    if existing is not None:
        record_id = existing.get("id")
        if same_record(existing, records): return f"SKIPPED: 已存在相同记录 id={record_id}"
        if args.on_existing == "skip": return f"CONFLICT_SKIPPED: 已存在不同记录 id={record_id}"
        if args.on_existing == "error": raise ImportFailure(f"{row.ptid}/{row.visit_date} 已存在不同记录 id={record_id}")
        if not record_id: raise ImportFailure(f"{row.ptid}/{row.visit_date} 既有记录缺少 id")
        api_post(requests, args, "/form/updateData", {"id": int(record_id), "formId": args.form_id, "records": records}); return f"UPDATED: id={record_id}"
    api_post(requests, args, "/form/insertData", {"formId": args.form_id, "records": records}); return "INSERTED"


def main() -> int:
    args = parse_args()
    try:
        psycopg2, requests = dependencies(); csv_rows, rejected = load_csv(args.csv); patients = query_patients(args, psycopg2)
        if args.patient_number:
            wanted = args.patient_number.strip()
            if wanted not in patients: raise ImportFailure(f"项目 {args.project_id} 中找不到 patient_number={wanted}")
            csv_rows = [row for row in csv_rows if row.ptid == wanted]; rejected = [row for row in rejected if row.ptid == wanted]
            if not csv_rows and not rejected: raise ImportFailure(f"CSV 中找不到 PTID={wanted}")
        rejected = [row for row in rejected if row.ptid in patients]
        matched = [row for row in csv_rows if row.ptid in patients]; outside_project = len(csv_rows) - len(matched); reject_duplicates(matched)
        grouped: dict[str, list[MocaRow]] = {}
        for row in matched: grouped.setdefault(row.ptid, []).append(row)
        results = list(rejected); mode = "commit" if args.commit else "dry-run"
        print(f"MoCA {mode}: 匹配 {len(grouped)} 位患者、{len(matched)} 条有效访视")
        for index, ptid in enumerate(sorted(grouped), start=1):
            patient = patients[ptid]; rows = sorted(grouped[ptid], key=lambda row: (row.visit_date, row.source_row)); print(f"[{index}/{len(grouped)}] {ptid} -> patient_id={patient.patient_id}, {len(rows)} 条")
            try:
                existing = query_existing(requests, args, patient.patient_id) if args.commit else {}
                for row in rows:
                    status = submit(requests, args, row, patient.patient_id, existing.get(row.visit_date)) if args.commit else "READY"
                    results.append(ResultRow(ptid, patient.patient_id, row.visit_date, row.viscode2, status)); print(f"  {row.visit_date} {row.viscode2 or '-'}: {status}")
            except ImportFailure as exc:
                message = str(exc); print(f"  ERROR: {message}", file=sys.stderr); done = {(item.ptid, item.visit_date) for item in results}
                for row in rows:
                    if (ptid, row.visit_date) not in done: results.append(ResultRow(ptid, patient.patient_id, row.visit_date, row.viscode2, "FAILED", message))
        counts: dict[str, int] = {}
        for item in results: counts[item.status.split(":", 1)[0]] = counts.get(item.status.split(":", 1)[0], 0) + 1
        report = {"mode": mode, "csv": str(args.csv), "project_id": args.project_id, "form_id": args.form_id, "matched_patients": len(grouped), "matched_valid_visits": len(matched), "valid_visits_outside_project": outside_project, "counts": counts, "results": [asdict(item) for item in results]}
        print(json.dumps({k: v for k, v in report.items() if k != "results"}, ensure_ascii=False, indent=2))
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True); args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"); print(f"报告已写入: {args.report}")
        if not args.commit: print("DRY-RUN: 未调用 RWE 查询或写入接口；确认后添加 --commit")
        return 2 if counts.get("FAILED", 0) else 0
    except ImportFailure as exc: print(f"ERROR: {exc}", file=sys.stderr); return 2
    except KeyboardInterrupt: print("ERROR: 用户取消", file=sys.stderr); return 130


if __name__ == "__main__": raise SystemExit(main())
