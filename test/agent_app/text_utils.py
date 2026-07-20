from __future__ import annotations

import ast
import operator


SUPPORTED_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def safe_math_eval(expression: str) -> str:
    """在不调用 Python ``eval`` 的情况下计算基本算术表达式。"""

    def calculate(node: ast.AST) -> float | int:
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            return node.value
        if isinstance(node, ast.BinOp):
            operator_function = SUPPORTED_OPERATORS.get(type(node.op))
            if operator_function is None:
                raise ValueError("表达式包含不支持的运算符。")
            return operator_function(calculate(node.left), calculate(node.right))

        if isinstance(node, ast.UnaryOp):
            operator_function = SUPPORTED_OPERATORS.get(type(node.op))
            if operator_function is None:
                raise ValueError("表达式包含不支持的运算符。")
            return operator_function(calculate(node.operand))

        raise ValueError("表达式只允许数字和基本数学运算。")

    return str(calculate(ast.parse(expression, mode="eval").body))
