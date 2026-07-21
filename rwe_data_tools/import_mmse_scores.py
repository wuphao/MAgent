#!/usr/bin/env python3
"""Import longitudinal MMSE detail records into RWE form 56."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_CSV = Path(r"C:\Users\admin\Downloads\MMSE_22Jun2026.csv")
DEFAULT_API_BASE_URL = "http://localhost:8080"
DEFAULT_DB_PASSWORD = "12345678"
DEFAULT_TOKEN = (
    "Bearer "
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJjbGFpbXMiOnsicm9sZSI6ImRvY3RvciIsInBob25lIjoiMTMwMjAzOTczNjYiLCJuYW1lIjoid3BoIiwiaWQiOjJ9LCJleHAiOjE3ODQ5NjM2MjB9."
    "N-I8dEEc0gKVAm6_Lsz8tmU5Pb90wvyJzpKZKVNJxqc"
)

YES_NO_FIELDS = {
    "MMDATE": "是否正确回答日期",
    "MMYEAR": "是否正确回答年份",
    "MMMONTH": "是否正确回答月份",
    "MMDAY": "是否正确回答星期几",
    "MMSEASON": "是否正确回答季节",
    "MMHOSPIT": "是否知道所在医院、机构或建筑",
    "MMFLOOR": "是否知道所在楼层",
    "MMCITY": "是否知道所在城市",
    "MMAREA": "是否知道所在地区、县或区域",
    "MMSTATE": "是否知道所在州或省",
    "WORD1": "是否立即记住并复述 ball",
    "WORD2": "是否立即记住并复述 flag",
    "WORD3": "是否立即记住并复述 tree",
    "WORD1DL": "延迟回忆第一个词是否正确",
    "WORD2DL": "延迟回忆第二个词是否正确",
    "WORD3DL": "延迟回忆第三个词是否正确",
}
SPECIAL_BINARY_FIELDS = {
    "MMWATCH": ("给患者看手表，询问“这是什么？”", "命名正确", "命名错误"),
    "MMPENCIL": ("给患者看铅笔，询问“这是什么？”", "命名正确", "命名错误"),
    "MMREPEAT": ("是否能准确重复指定句子", "完整正确重复", "未正确重复"),
    "MMHAND": ("用右手拿起纸", "正确执行", "未正确执行"),
    "MMFOLD": ("将纸对折", "正确执行", "未正确执行"),
    "MMONFLR": ("把纸放在地板上", "正确执行", "未正确执行"),
    "MMREAD": ("阅读并执行纸上的命令", "正确执行", "未正确执行"),
    "MMWRITE": ("写出一个完整、有意义的句子", "符合要求", "不符合要求"),
    "MMDRAW": ("临摹指定的几何图形", "临摹符合评分标准", "未达到标准"),
}
INTEGER_FIELDS = {
    "MMTRIALS": "受试者经过多少次尝试才学会这三个词",
    "WORLDSCORE": "倒拼WORLD总得分",
    "MMSCORE": "MMSE总分",
}
TEXT_FIELDS = {
    "MMLTR1": "受试者说出的第 1 个字母",
    "MMLTR2": "受试者说出的第 2 个字母",
    "MMLTR3": "受试者说出的第 3 个字母",
    "MMLTR4": "受试者说出的第 4 个字母",
    "MMLTR5": "受试者说出的第 5 个字母",
    "MMLTR6": "如果多说了，记录第 6 个字母",
    "MMLTR7": "如果继续多说，记录第 7 个字母",
}


class ImportFailure(RuntimeError):
    pass


@dataclass(frozen=True)
class MmseRow:
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
    parser = argparse.ArgumentParser(description="Import MMSE records into RWE form 56.")
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--project-id", type=int, default=8)
    parser.add_argument("--form-id", type=int, default=56)
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


def parse_binary(value: Any, label: str, row_number: int, positive: str, negative: str) -> str | None:
    text = clean(value)
    if not text or text in {"-1", "-1.0"}:
        return None
    if text in {"1", "1.0"}:
        return positive
    if text in {"0", "0.0"}:
        return negative
    raise ImportFailure(f"第 {row_number} 行 {label} 不是 0/1/空: {text}")


def parse_integer(value: Any, label: str, row_number: int) -> int | None:
    text = clean(value)
    if not text or text in {"-1", "-1.0"}:
        return None
    try:
        number = float(text)
    except ValueError as exc:
        raise ImportFailure(f"第 {row_number} 行 {label} 不是数字: {text}") from exc
    if not number.is_integer():
        raise ImportFailure(f"第 {row_number} 行 {label} 不是整数: {text}")
    result = int(number)
    limits = {"MMTRIALS": (0, 20), "WORLDSCORE": (0, 5), "MMSCORE": (0, 30)}
    lower, upper = limits[label]
    if not lower <= result <= upper:
        raise ImportFailure(f"第 {row_number} 行 {label} 超出 {lower}～{upper}: {result}")
    return result


def load_csv(path: Path) -> tuple[list[MmseRow], list[ResultRow]]:
    if not path.is_file():
        raise ImportFailure(f"CSV 不存在: {path}")
    source_columns = {"PTID", "VISDATE", *YES_NO_FIELDS, *SPECIAL_BINARY_FIELDS, *INTEGER_FIELDS, *TEXT_FIELDS}
    rows: list[MmseRow] = []
    rejected: list[ResultRow] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = sorted(source_columns - set(reader.fieldnames or []))
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
                for source, target in YES_NO_FIELDS.items():
                    value = parse_binary(raw.get(source), source, row_number, "是", "否")
                    if value is not None:
                        values[target] = value
                for source, (target, positive, negative) in SPECIAL_BINARY_FIELDS.items():
                    value = parse_binary(raw.get(source), source, row_number, positive, negative)
                    if value is not None:
                        values[target] = value
                for source, target in INTEGER_FIELDS.items():
                    value = parse_integer(raw.get(source), source, row_number)
                    if value is not None:
                        values[target] = value
                for source, target in TEXT_FIELDS.items():
                    value = clean(raw.get(source))
                    if value:
                        values[target] = value
            except ImportFailure as exc:
                rejected.append(ResultRow(ptid, None, clean(raw.get("VISDATE")), viscode2, "FAILED", str(exc)))
                continue
            if not values:
                rejected.append(ResultRow(ptid, None, visit_date, viscode2, "EMPTY_SCORES", "所有保留字段均为空"))
                continue
            rows.append(MmseRow(row_number, ptid, viscode2, visit_date, values))
    return rows, rejected


def reject_duplicates(rows: list[MmseRow]) -> None:
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
    connection = psycopg2.connect(
        host=args.db_host, port=args.db_port, dbname=args.db_name,
        user=args.db_user, password=args.db_password, connect_timeout=10,
    )
    try:
        connection.set_session(readonly=True, autocommit=True)
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT TRIM(pp.patient_number), pp.patient_id
                FROM patient_project pp JOIN patient p ON p.id=pp.patient_id
                WHERE pp.project_id=%s AND pp.is_delete=0 AND p.is_delete=0
                  AND pp.patient_number IS NOT NULL AND TRIM(pp.patient_number)<>''
            """, (args.project_id,))
            records = cursor.fetchall()
    finally:
        connection.close()
    return {number: PatientRef(number, int(patient_id)) for number, patient_id in records}


def auth(token: str) -> str:
    token = clean(token)
    if not token:
        raise ImportFailure("API Token 为空")
    return token if token.lower().startswith("bearer ") else f"Bearer {token}"


def api_post(requests: Any, args: argparse.Namespace, path: str, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        response = requests.post(
            f"{args.api_base_url.rstrip('/')}{path}", json=payload,
            headers={"Authorization": auth(args.token), "Content-Type": "application/json"},
            timeout=args.timeout,
        )
        response.raise_for_status()
        result = response.json()
    except requests.RequestException as exc:
        raise ImportFailure(f"API 请求失败 {path}: {exc}") from exc
    except ValueError as exc:
        raise ImportFailure(f"API 返回非 JSON: {path}") from exc
    if not isinstance(result, dict) or result.get("code") != 0:
        message = result.get("message", result) if isinstance(result, dict) else result
        raise ImportFailure(f"API 业务失败 {path}: {message}")
    return result


def query_existing(requests: Any, args: argparse.Namespace, patient_id: int) -> dict[str, dict[str, Any]]:
    result = api_post(requests, args, "/form/queryData", {
        "formId": args.form_id, "page": 0, "pageSize": 0,
        "criteria": [{"enName": "patient_id", "inputValue": patient_id, "isFuzzy": False}],
    })
    existing: dict[str, dict[str, Any]] = {}
    for item in ((result.get("data") or {}).get("list") or []):
        try:
            date = parse_date(item.get("访视日期"), 0)
        except ImportFailure:
            continue
        if date in existing:
            raise ImportFailure(f"患者 {patient_id} 在 {date} 有多条既有 MMSE 记录")
        existing[date] = item
    return existing


def build_records(row: MmseRow, patient_id: int) -> dict[str, Any]:
    return {"patient_id": patient_id, "访视日期": row.visit_date, **row.values}


def same_record(existing: dict[str, Any], desired: dict[str, Any]) -> bool:
    for field, value in desired.items():
        if field in {"patient_id", "访视日期"}:
            continue
        old = existing.get(field)
        if isinstance(value, int):
            try:
                if int(float(str(old))) != value:
                    return False
            except (TypeError, ValueError):
                return False
        elif clean(old) != clean(value):
            return False
    return True


def submit(requests: Any, args: argparse.Namespace, row: MmseRow, patient_id: int, existing: dict[str, Any] | None) -> str:
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
        psycopg2, requests = dependencies()
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
        reject_duplicates(matched)
        grouped: dict[str, list[MmseRow]] = {}
        for row in matched:
            grouped.setdefault(row.ptid, []).append(row)

        results = list(rejected)
        mode = "commit" if args.commit else "dry-run"
        print(f"MMSE {mode}: 匹配 {len(grouped)} 位患者、{len(matched)} 条有效访视")
        for index, ptid in enumerate(sorted(grouped), start=1):
            patient = patients[ptid]
            rows = sorted(grouped[ptid], key=lambda row: (row.visit_date, row.source_row))
            print(f"[{index}/{len(grouped)}] {ptid} -> patient_id={patient.patient_id}, {len(rows)} 条")
            try:
                existing = query_existing(requests, args, patient.patient_id) if args.commit else {}
                for row in rows:
                    status = submit(requests, args, row, patient.patient_id, existing.get(row.visit_date)) if args.commit else "READY"
                    results.append(ResultRow(ptid, patient.patient_id, row.visit_date, row.viscode2, status))
                    print(f"  {row.visit_date} {row.viscode2 or '-'}: {status}")
            except ImportFailure as exc:
                message = str(exc)
                print(f"  ERROR: {message}", file=sys.stderr)
                done = {(item.ptid, item.visit_date) for item in results}
                for row in rows:
                    if (ptid, row.visit_date) not in done:
                        results.append(ResultRow(ptid, patient.patient_id, row.visit_date, row.viscode2, "FAILED", message))

        counts: dict[str, int] = {}
        for item in results:
            category = item.status.split(":", 1)[0]
            counts[category] = counts.get(category, 0) + 1
        report = {
            "mode": mode, "csv": str(args.csv), "project_id": args.project_id, "form_id": args.form_id,
            "matched_patients": len(grouped), "matched_valid_visits": len(matched),
            "valid_visits_outside_project": outside_project, "counts": counts,
            "results": [asdict(item) for item in results],
        }
        print(json.dumps({key: value for key, value in report.items() if key != "results"}, ensure_ascii=False, indent=2))
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
