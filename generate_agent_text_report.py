"""Generate one plain-text paragraph from an already completed Agent JSON."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from llm_client import DeepSeekClient


AGENT_NAMES = (
    "认知量表Agent",
    "功能分期Agent",
    "纵向统计Agent",
    "生物标志物Agent",
    "影像Agent",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Read a completed multi-Agent JSON and write one DeepSeek-generated TXT report."
    )
    parser.add_argument("agent_result", type=Path, help="由 main.py --full 生成的 Agent 结果JSON")
    parser.add_argument("--output", type=Path, help="TXT输出路径")
    return parser.parse_args()


def extract_payload(document: dict[str, Any]) -> dict[str, Any]:
    outputs = document.get("agent_outputs")
    if not isinstance(outputs, dict):
        raise ValueError("输入文件不含 agent_outputs；请传入 main.py --full 生成的JSON")
    missing = [name for name in AGENT_NAMES if name not in outputs]
    if missing:
        raise ValueError("Agent结果缺失: " + "、".join(missing))

    normalized = document.get("normalized_case") or {}
    raw_case = document.get("raw_case") or {}
    patient = normalized.get("patient") or raw_case.get("patient") or {}
    return {
        "patient_number": patient.get("patient_number"),
        "five_agent_results": {name: outputs[name] for name in AGENT_NAMES},
    }


def generate_report(payload: dict[str, Any]) -> str:
    messages = [
        {
            "role": "system",
            "content": (
                "你是认知障碍真实世界研究报告助手。根据用户提供的五个Agent结果写一段连贯、"
                "简洁但信息完整的中文可解释性报告。必须综合认知量表、功能分期、纵向变化、"
                "生物标志物和MRI/PET影像结果；说明相互支持或冲突之处、数据局限和不确定性。"
                "不得杜撰原文没有的数值、日期、影像发现或诊断，不得把研究模型预测表述为临床确诊。"
                "正文不要标题、列表、Markdown或换行。只返回JSON：{\"report_text\": \"一段正文\"}。"
            ),
        },
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]
    result = DeepSeekClient().chat_json(messages, temperature=0.0, num_predict=1800)
    if not isinstance(result, dict) or not isinstance(result.get("report_text"), str):
        raise ValueError("DeepSeek返回结果缺少 report_text")
    text = result["report_text"].strip()
    if not text:
        raise ValueError("DeepSeek返回了空报告")
    return re.sub(r"\s+", " ", text)


def main() -> int:
    args = parse_args()
    document = json.loads(args.agent_result.read_text(encoding="utf-8"))
    payload = extract_payload(document)
    report_text = generate_report(payload)
    output = args.output or args.agent_result.with_name(
        args.agent_result.stem.removesuffix("_agent_result") + "_report.txt"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(report_text + "\n", encoding="utf-8")
    print(str(output.resolve()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
