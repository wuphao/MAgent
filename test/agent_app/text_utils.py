from __future__ import annotations

import ast
import operator as op
import re
from datetime import datetime
from pathlib import Path
from typing import Any


def safe_filename(name: str) -> str:
    clean = Path(name).name.strip()
    clean = re.sub(r"[^0-9A-Za-z._\-\u4e00-\u9fff]+", "_", clean)
    return clean or f"upload_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"


def message_content_to_text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                if isinstance(item.get("text"), str):
                    parts.append(item["text"])
                elif isinstance(item.get("content"), str):
                    parts.append(item["content"])
                else:
                    parts.append(str(item))
            else:
                parts.append(str(item))
        return "".join(parts)
    return str(content)


def extract_text_from_model_output(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if hasattr(value, "content"):
        text = message_content_to_text(getattr(value, "content"))
        if text.strip():
            return text
    if isinstance(value, dict):
        for key in ("output", "answer", "content", "text"):
            if key in value:
                text = extract_text_from_model_output(value[key])
                if text.strip():
                    return text
        for item in reversed(list(value.values())):
            text = extract_text_from_model_output(item)
            if text.strip():
                return text
        return ""
    if isinstance(value, (list, tuple)):
        for item in reversed(value):
            text = extract_text_from_model_output(item)
            if text.strip():
                return text
        return ""
    return ""


def extract_stream_text(event: Any) -> str:
    if event is None:
        return ""
    if isinstance(event, tuple) and event:
        first = event[0]
        if hasattr(first, "content"):
            return message_content_to_text(first.content)
        if isinstance(first, dict):
            text = extract_text_from_model_output(first)
            if text.strip():
                return text
    if hasattr(event, "content"):
        return message_content_to_text(event.content)
    if isinstance(event, dict):
        text = extract_text_from_model_output(event)
        if text.strip():
            return text
    if isinstance(event, str):
        return event
    return ""


def safe_math_eval(expression: str) -> str:
    allowed_ops = {
        ast.Add: op.add,
        ast.Sub: op.sub,
        ast.Mult: op.mul,
        ast.Div: op.truediv,
        ast.FloorDiv: op.floordiv,
        ast.Mod: op.mod,
        ast.Pow: op.pow,
        ast.USub: op.neg,
        ast.UAdd: op.pos,
    }

    def _eval(node: ast.AST) -> float:
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        if isinstance(node, ast.Num):  # pragma: no cover - legacy AST nodes
            return float(node.n)
        if isinstance(node, ast.BinOp) and type(node.op) in allowed_ops:
            return float(allowed_ops[type(node.op)](_eval(node.left), _eval(node.right)))
        if isinstance(node, ast.UnaryOp) and type(node.op) in allowed_ops:
            return float(allowed_ops[type(node.op)](_eval(node.operand)))
        raise ValueError("表达式只允许数字和基本四则运算。")

    tree = ast.parse(expression, mode="eval")
    return str(_eval(tree.body))

