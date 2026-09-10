"""Refresh the local RWE token without storing a login password."""
import argparse
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from multi_agent.ingestion.rwe_export import local_settings


def main():
    import requests

    parser = argparse.ArgumentParser()
    parser.add_argument("--phone", required=True)
    args = parser.parse_args()
    config = Path(__file__).resolve().parents[1] / ".env.rwe.local"
    settings = local_settings(config)
    base = settings.get("RWE_API_BASE_URL", "http://localhost:8081").rstrip("/")
    password = getpass.getpass("RWE password: ")
    response = requests.post(base + "/account/login", json={"phone": args.phone, "password": password}, timeout=20)
    if response.status_code != 200:
        raise SystemExit(f"登录失败（HTTP {response.status_code}）")
    data = response.json()
    token = (data.get("data") or {}).get("token")
    if data.get("code") != 0 or not isinstance(token, str) or not token:
        raise SystemExit("登录失败：未取得 Token")
    lines = config.read_text(encoding="utf-8-sig").splitlines() if config.exists() else []
    lines = [line for line in lines if not line.startswith("RWE_API_TOKEN=")]
    config.write_text("\n".join(lines + ["RWE_API_TOKEN=" + token]) + "\n", encoding="utf-8")
    print("登录成功，已更新本机 Token；未保存密码。")


if __name__ == "__main__":
    main()
