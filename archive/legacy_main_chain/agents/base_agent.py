from __future__ import annotations

import json
from typing import Any

from llm_client import DeepSeekClient


class BaseAgent:
    """Shared plumbing for RWE agents.

    Agents always produce deterministic output first.  LLM use is optional and
    must never replace scores, dates, record ids, or quality flags.
    """

    name = ""

    def __init__(self, llm_client: DeepSeekClient | None = None, use_llm: bool = False):
        self.llm_client = llm_client or DeepSeekClient()
        self.use_llm = use_llm

    def analyze(self, memory: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    def run(self, memory: dict[str, Any]) -> dict[str, Any]:
        output = self.analyze(memory)
        if self.use_llm:
            output["llm_analysis"] = self._specialist_llm_analysis(output)
        memory.setdefault("agent_outputs", {})[self.name] = output
        return memory

    def _specialist_llm_analysis(self, deterministic_output: dict[str, Any]) -> dict[str, Any]:
        """Interpret immutable tool output without replacing it."""
        fallback = {
            "status": "fallback",
            "summary": "DeepSeek专业分析未完成，保留Python或模型产生的结构化结果。",
            "interpretation": [],
            "evidence_reasoning": [],
            "uncertainties": ["大模型分析不可用"],
            "recommendations": [],
        }
        messages = [
            {
                "role": "system",
                "content": (
                    f"你是{self.name}。请对给定的结构化计算结果进行本专业分析。"
                    "Python统计、量表得分、日期、record_id、DiaMond预测和原始证据都是不可修改的事实。"
                    "不得补造数据，不得将研究信号或模型分类表述为临床确诊。"
                    "请输出合法JSON，严格包含status、summary、interpretation、evidence_reasoning、"
                    "uncertainties、recommendations；后四项均为字符串数组，status写success。"
                ),
            },
            {"role": "user", "content": json.dumps(deterministic_output, ensure_ascii=False)},
        ]
        try:
            value = self.llm_client.chat_json(messages, temperature=0.0, num_predict=1000)
            if not isinstance(value, dict) or not isinstance(value.get("summary"), str):
                return fallback
            result = {"status": "success", "summary": value["summary"].strip()}
            for field in ("interpretation", "evidence_reasoning", "uncertainties", "recommendations"):
                items = value.get(field)
                result[field] = [str(item).strip() for item in items] if isinstance(items, list) else []
            return result
        except Exception as exc:
            fallback["uncertainties"] = [f"大模型分析不可用：{type(exc).__name__}"]
            return fallback

    @staticmethod
    def evidence(form: str, record: dict[str, Any], finding: str) -> dict[str, Any]:
        return {
            "form": form,
            "record_id": record.get("record_id"),
            "date": record.get("visit_date"),
            "finding": finding,
        }

    def llm_reason(
        self,
        system_prompt: str,
        user_payload: str,
        default_output: dict[str, Any],
    ) -> dict[str, Any]:
        if not self.use_llm:
            return default_output
        messages = [
            {
                "role": "system",
                "content": system_prompt + "\n只返回合法JSON，不要Markdown或额外解释。",
            },
            {"role": "user", "content": user_payload},
        ]
        result = self.llm_client.chat_json(messages, default=default_output)
        return result if isinstance(result, dict) else default_output
