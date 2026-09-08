#!/usr/bin/env python3
"""Import one patient's DICOM demographics into RWE form 87.

The database is used for read-only patient-number lookup. All form writes go
through the RWE HTTP API. Dry-run is the default; pass --commit to write.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


DEFAULT_SOURCE_DIR = Path(r"D:\data\adni_diamond\MCI")
DEFAULT_PROJECT_ID = 8
DEFAULT_FORM_ID = 87
DEFAULT_API_BASE_URL = "http://localhost:8080"
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
class PatientMatch:
    patient_number: str
    patient_id: int
    directory: Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Read DICOM demographics and submit them to an RWE form.",
    )
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIR)
    parser.add_argument("--project-id", type=int, default=DEFAULT_PROJECT_ID)
    parser.add_argument("--form-id", type=int, default=DEFAULT_FORM_ID)
    parser.add_argument(
        "--diagnosis",
        choices=("AD", "MCI", "CN"),
        help="Value for 患病情况; defaults to the source directory name.",
    )
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument(
        "--patient-number",
        help="Import this ADNI/RWE patient number; otherwise use the first match.",
    )
    selection.add_argument(
        "--all-patients",
        action="store_true",
        help="Process every source directory matched to a patient in the project.",
    )
    parser.add_argument("--api-base-url", default=DEFAULT_API_BASE_URL)
    parser.add_argument("--token", default=DEFAULT_RWE_TOKEN, help="JWT or 'Bearer <JWT>'.")
    parser.add_argument("--db-host", default=os.getenv("RWE_DB_HOST", "localhost"))
    parser.add_argument("--db-port", type=int, default=int(os.getenv("RWE_DB_PORT", "5432")))
    parser.add_argument("--db-name", default=os.getenv("RWE_DB_NAME", "rwe_nexus_develop"))
    parser.add_argument("--db-user", default=os.getenv("RWE_DB_USER", "postgres"))
    parser.add_argument("--db-password", default=DEFAULT_DB_PASSWORD)
    parser.add_argument(
        "--on-existing",
        choices=("skip", "update", "error"),
        default="skip",
        help="Action when this single-fill form already has a row.",
    )
    parser.add_argument("--sample-files", type=int, default=5, help="DICOM files checked for consistency.")
    parser.add_argument("--timeout", type=float, default=30.0, help="HTTP timeout in seconds.")
    parser.add_argument("--commit", action="store_true", help="Actually call insertData/updateData.")
    return parser.parse_args()


def require_dependencies() -> tuple[Any, Any, Any]:
    missing: list[str] = []
    try:
        import psycopg2
    except ImportError:
        psycopg2 = None
        missing.append("psycopg2-binary")
    try:
        import pydicom
    except ImportError:
        pydicom = None
        missing.append("pydicom")
    try:
        import requests
    except ImportError:
        requests = None
        missing.append("requests")
    if missing:
        raise ImportFailure("缺少依赖，请先安装: " + " ".join(missing))
    return psycopg2, pydicom, requests


def clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip().strip("\x00")
    return text or None


def query_patient_matches(args: argparse.Namespace, psycopg2: Any) -> list[PatientMatch]:
    if not args.db_password:
        raise ImportFailure("未提供数据库密码，请设置 RWE_DB_PASSWORD。")
    if not args.source_dir.is_dir():
        raise ImportFailure(f"DICOM 根目录不存在: {args.source_dir}")

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
            rows = cursor.fetchall()
    finally:
        connection.close()

    matches: list[PatientMatch] = []
    for patient_number, patient_id in rows:
        directory = args.source_dir / patient_number
        if directory.is_dir():
            matches.append(PatientMatch(patient_number, int(patient_id), directory))
    return matches


def select_patient(args: argparse.Namespace, matches: list[PatientMatch]) -> PatientMatch:
    if not matches:
        raise ImportFailure(
            f"项目 {args.project_id} 的 patient_number 与 {args.source_dir} 没有匹配项。"
        )
    if args.patient_number:
        wanted = args.patient_number.strip()
        for match in matches:
            if match.patient_number == wanted:
                return match
        available = ", ".join(item.patient_number for item in matches)
        raise ImportFailure(f"患者编号 {wanted} 不在可导入列表中。可用: {available}")
    return matches[0]


def dicom_files(directory: Path) -> list[Path]:
    files = sorted(
        (path for path in directory.rglob("*") if path.is_file() and path.suffix.lower() == ".dcm"),
        key=lambda path: str(path).lower(),
    )
    if not files:
        raise ImportFailure(f"患者目录中没有 .dcm 文件: {directory}")
    return files


def read_dicom_headers(files: Iterable[Path], pydicom: Any, limit: int) -> list[tuple[Path, Any]]:
    headers: list[tuple[Path, Any]] = []
    errors: list[str] = []
    for path in files:
        if len(headers) >= limit:
            break
        try:
            dataset = pydicom.dcmread(str(path), stop_before_pixels=True)
            headers.append((path, dataset))
        except Exception as exc:  # keep looking for another valid DICOM
            errors.append(f"{path}: {exc}")
    if not headers:
        details = errors[0] if errors else "未知原因"
        raise ImportFailure(f"没有可读取的 DICOM 文件。首个错误: {details}")
    return headers


def consistent_value(headers: list[tuple[Path, Any]], keyword: str) -> Any:
    observed: dict[str, Any] = {}
    for path, dataset in headers:
        value = getattr(dataset, keyword, None)
        normalized = clean_text(value)
        if normalized is not None:
            observed[normalized] = value
    if len(observed) > 1:
        values = ", ".join(sorted(observed))
        raise ImportFailure(f"抽查的 DICOM 中 {keyword} 不一致: {values}")
    return next(iter(observed.values()), None)


def parse_age(value: Any) -> int | None:
    text = clean_text(value)
    if text is None:
        return None
    match = re.fullmatch(r"(\d{3})([YMWD])", text.upper())
    if not match:
        raise ImportFailure(f"PatientAge 格式不合法: {text}")
    amount, unit = int(match.group(1)), match.group(2)
    if unit == "Y":
        years = amount
    elif unit == "M":
        years = amount // 12
    elif unit == "W":
        years = amount // 52
    else:
        years = amount // 365
    if not 0 <= years <= 150:
        raise ImportFailure(f"转换后的年龄超出合理范围: {years}")
    return years


def parse_positive_float(value: Any, label: str, maximum: float) -> float | None:
    text = clean_text(value)
    if text is None:
        return None
    try:
        result = float(text)
    except ValueError as exc:
        raise ImportFailure(f"{label} 不是合法数字: {text}") from exc
    if not 0 < result <= maximum:
        raise ImportFailure(f"{label} 超出合理范围: {result}")
    return result


def parse_height_cm(value: Any) -> float | None:
    text = clean_text(value)
    if text is None:
        return None
    try:
        height = float(text)
    except ValueError as exc:
        raise ImportFailure(f"身高不是合法数字: {text}") from exc

    # DICOM PatientSize is normally expressed in metres. Some source data may
    # already use centimetres, so values below 2.5 are converted to cm.
    height_cm = height * 100 if height < 2.5 else height
    if not 30 <= height_cm <= 250:
        raise ImportFailure(f"转换后的身高超出合理范围: {height_cm} cm")
    return height_cm


def parse_birth_date(value: Any) -> str | None:
    text = clean_text(value)
    if text is None:
        return None
    try:
        return datetime.strptime(text, "%Y%m%d").strftime("%Y-%m-%d")
    except ValueError as exc:
        raise ImportFailure(f"PatientBirthDate 格式不合法: {text}") from exc


def parse_sex(value: Any) -> str:
    text = (clean_text(value) or "").upper()
    return {"M": "男", "F": "女"}.get(text, "未知")


def resolve_diagnosis(args: argparse.Namespace) -> str:
    if args.diagnosis:
        return args.diagnosis
    diagnosis = args.source_dir.resolve().name.upper()
    if diagnosis not in {"AD", "MCI", "CN"}:
        raise ImportFailure(
            f"无法从目录名 {args.source_dir.name!r} 判断患病情况，请指定 --diagnosis AD|MCI|CN。"
        )
    return diagnosis


def build_records(
    match: PatientMatch,
    headers: list[tuple[Path, Any]],
    diagnosis: str,
) -> tuple[dict[str, Any], list[str]]:
    patient_id_tag = clean_text(consistent_value(headers, "PatientID"))
    if patient_id_tag != match.patient_number:
        raise ImportFailure(
            f"DICOM PatientID={patient_id_tag!r} 与 patient_number={match.patient_number!r} 不一致。"
        )

    records: dict[str, Any] = {
        "patient_id": match.patient_id,
        "年龄": parse_age(consistent_value(headers, "PatientAge")),
        "身高": parse_height_cm(consistent_value(headers, "PatientSize")),
        "体重": parse_positive_float(consistent_value(headers, "PatientWeight"), "体重", 500.0),
        "出生日期": parse_birth_date(consistent_value(headers, "PatientBirthDate")),
        "性别": parse_sex(consistent_value(headers, "PatientSex")),
        "患病情况": diagnosis,
    }
    optional_fields = ("年龄", "身高", "体重", "出生日期", "性别")
    missing = [name for name in optional_fields if records[name] is None]
    # Do not submit null for optional fields. Omitting the key avoids clearing an
    # existing value during update and lets the backend apply current form rules.
    records = {key: value for key, value in records.items() if value is not None}
    if not records.get("患病情况"):
        raise ImportFailure("患病情况不能为空。")
    return records, missing


def authorization_header(token: str | None) -> str:
    if not token or not token.strip():
        raise ImportFailure("未提供 API Token，请设置 RWE_TOKEN 或使用 --token。")
    cleaned = token.strip()
    return cleaned if cleaned.lower().startswith("bearer ") else f"Bearer {cleaned}"


def api_post(requests: Any, url: str, authorization: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
    try:
        response = requests.post(
            url,
            json=payload,
            headers={"Authorization": authorization, "Content-Type": "application/json"},
            timeout=timeout,
        )
        response.raise_for_status()
        result = response.json()
    except requests.RequestException as exc:
        raise ImportFailure(f"API 请求失败: {url}: {exc}") from exc
    except ValueError as exc:
        raise ImportFailure(f"API 未返回合法 JSON: {url}") from exc
    if not isinstance(result, dict):
        raise ImportFailure(f"API 返回结构不正确: {url}")
    return result


def query_existing_record(
    requests: Any,
    api_base_url: str,
    authorization: str,
    form_id: int,
    patient_id: int,
    timeout: float,
) -> dict[str, Any] | None:
    payload = {
        "formId": form_id,
        "page": 0,
        "pageSize": 0,
        "criteria": [{"enName": "patient_id", "inputValue": patient_id, "isFuzzy": False}],
    }
    result = api_post(
        requests,
        f"{api_base_url.rstrip('/')}/form/queryData",
        authorization,
        payload,
        timeout,
    )
    if result.get("code") != 0:
        raise ImportFailure(f"查询既有记录失败: {result.get('message', result)}")
    rows = ((result.get("data") or {}).get("list") or [])
    if len(rows) > 1:
        raise ImportFailure(f"单次填写表单发现 {len(rows)} 条有效记录，请先处理重复数据。")
    return rows[0] if rows else None


def submit_records(
    args: argparse.Namespace,
    requests: Any,
    authorization: str,
    records: dict[str, Any],
) -> str:
    existing = query_existing_record(
        requests,
        args.api_base_url,
        authorization,
        args.form_id,
        int(records["patient_id"]),
        args.timeout,
    )
    if existing and args.on_existing == "skip":
        return f"SKIPPED: 已存在记录 id={existing.get('id')}"
    if existing and args.on_existing == "error":
        raise ImportFailure(f"患者已有表单记录 id={existing.get('id')}")

    base_url = args.api_base_url.rstrip("/")
    if existing:
        endpoint = f"{base_url}/form/updateData"
        payload = {"id": int(existing["id"]), "formId": args.form_id, "records": records}
        action = "UPDATED"
    else:
        endpoint = f"{base_url}/form/insertData"
        payload = {"formId": args.form_id, "records": records}
        action = "INSERTED"

    result = api_post(requests, endpoint, authorization, payload, args.timeout)
    if result.get("code") != 0:
        raise ImportFailure(f"提交失败: {result.get('message', result)}")
    return f"{action}: {result.get('message', '操作成功')}"


def prepare_patient(
    match: PatientMatch,
    pydicom: Any,
    sample_files: int,
    diagnosis: str,
) -> tuple[dict[str, Any], list[str], list[Path]]:
    files = dicom_files(match.directory)
    headers = read_dicom_headers(files, pydicom, max(1, sample_files))
    records, missing_fields = build_records(match, headers, diagnosis)
    return records, missing_fields, [path for path, _ in headers]


def print_patient_summary(
    args: argparse.Namespace,
    match: PatientMatch,
    records: dict[str, Any],
    missing_fields: list[str],
    sampled_paths: list[Path],
) -> None:
    summary = {
        "mode": "commit" if args.commit else "dry-run",
        "project_id": args.project_id,
        "form_id": args.form_id,
        "patient_number": match.patient_number,
        "patient_id": match.patient_id,
        "dicom_directory": str(match.directory),
        "sampled_dicom_files": [str(path) for path in sampled_paths],
        "omitted_missing_optional_fields": missing_fields,
        "records": records,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def process_all_patients(
    args: argparse.Namespace,
    matches: list[PatientMatch],
    pydicom: Any,
    requests: Any,
    diagnosis: str,
) -> int:
    authorization = authorization_header(args.token) if args.commit else None
    results: list[dict[str, Any]] = []

    print(f"BATCH: 找到 {len(matches)} 个项目患者与 DICOM 目录匹配。")
    for index, match in enumerate(matches, start=1):
        print(f"\n[{index}/{len(matches)}] {match.patient_number} (patient_id={match.patient_id})")
        try:
            records, missing_fields, sampled_paths = prepare_patient(
                match, pydicom, args.sample_files, diagnosis
            )
            print_patient_summary(args, match, records, missing_fields, sampled_paths)
            if args.commit:
                status = submit_records(args, requests, authorization, records)
            else:
                status = "DRY-RUN"
            print(status)
            results.append({"patient_number": match.patient_number, "patient_id": match.patient_id, "status": status})
        except ImportFailure as exc:
            message = str(exc)
            print(f"ERROR: {message}", file=sys.stderr)
            results.append(
                {
                    "patient_number": match.patient_number,
                    "patient_id": match.patient_id,
                    "status": "FAILED",
                    "error": message,
                }
            )

    failed = sum(item["status"] == "FAILED" for item in results)
    skipped = sum(str(item["status"]).startswith("SKIPPED") for item in results)
    succeeded = len(results) - failed - skipped
    print("\nBATCH SUMMARY")
    print(
        json.dumps(
            {
                "mode": "commit" if args.commit else "dry-run",
                "total": len(results),
                "succeeded_or_ready": succeeded,
                "skipped": skipped,
                "failed": failed,
                "results": results,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 2 if failed else 0


def main() -> int:
    args = parse_args()
    try:
        psycopg2, pydicom, requests = require_dependencies()
        diagnosis = resolve_diagnosis(args)
        matches = query_patient_matches(args, psycopg2)
        if args.all_patients:
            if not matches:
                raise ImportFailure(
                    f"项目 {args.project_id} 的 patient_number 与 {args.source_dir} 没有匹配项。"
                )
            return process_all_patients(args, matches, pydicom, requests, diagnosis)

        match = select_patient(args, matches)
        records, missing_fields, sampled_paths = prepare_patient(
            match, pydicom, args.sample_files, diagnosis
        )
        print_patient_summary(args, match, records, missing_fields, sampled_paths)

        if not args.commit:
            print("DRY-RUN: 未调用 RWE 写入接口。确认数据后添加 --commit。")
            return 0

        authorization = authorization_header(args.token)
        print(submit_records(args, requests, authorization, records))
        return 0
    except ImportFailure as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("ERROR: 用户取消。", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
