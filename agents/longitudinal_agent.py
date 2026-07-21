from __future__ import annotations

from datetime import date
from typing import Any

from agents.base_agent import BaseAgent


class LongitudinalAgent(BaseAgent):
    name = "纵向统计Agent"

    DIRECTIONS = {
        "mmse": -1,
        "moca": -1,
        "adas13": 1,
        "adas11": 1,
    }

    def analyze(self, memory: dict[str, Any]) -> dict[str, Any]:
        cognition = memory["agent_outputs"]["认知量表Agent"]
        trajectories = {}
        for name, series in cognition["score_series"].items():
            trajectories[name] = self._trajectory(series, self.DIRECTIONS[name])

        usable = [item for item in trajectories.values() if item.get("n", 0) >= 2]
        worsening = sum(item.get("direction") == "worsening" for item in usable)
        pattern = "多量表支持下降" if worsening >= 2 else "单量表下降或结果不一致" if worsening else "未见明确下降"
        return {
            "domain": "longitudinal",
            "overall_pattern": pattern,
            "trajectories": trajectories,
            "limitations": ["单患者少量时间点的斜率用于描述，不代表因果效应或人群推断"],
        }

    def _trajectory(self, series: list[dict[str, Any]], worsening_sign: int) -> dict[str, Any]:
        if not series:
            return {"n": 0, "status": "unavailable"}
        if len(series) == 1:
            return {"n": 1, "status": "insufficient", "baseline": series[0]["score"]}

        dated = [item for item in series if item.get("date")]
        if len(dated) < 2:
            return {"n": len(series), "status": "insufficient_dates"}
        origin = date.fromisoformat(dated[0]["date"])
        xs = [(date.fromisoformat(item["date"]) - origin).days / 365.25 for item in dated]
        ys = [float(item["score"]) for item in dated]
        slope, r2 = self._ols(xs, ys)
        change = ys[-1] - ys[0]
        worsening = change * worsening_sign > 0
        monotonic = all((ys[i] - ys[i - 1]) * worsening_sign >= 0 for i in range(1, len(ys)))
        return {
            "n": len(ys),
            "status": "analyzed",
            "baseline_date": dated[0]["date"],
            "latest_date": dated[-1]["date"],
            "followup_years": round(xs[-1], 2),
            "baseline": ys[0],
            "latest": ys[-1],
            "absolute_change": round(change, 3),
            "annual_slope": round(slope, 3),
            "r_squared": round(r2, 3),
            "direction": "worsening" if worsening else "improving_or_stable",
            "pattern": "monotonic" if monotonic else "non_monotonic",
        }

    @staticmethod
    def _ols(xs: list[float], ys: list[float]) -> tuple[float, float]:
        xbar = sum(xs) / len(xs)
        ybar = sum(ys) / len(ys)
        denominator = sum((x - xbar) ** 2 for x in xs)
        slope = sum((x - xbar) * (y - ybar) for x, y in zip(xs, ys)) / denominator if denominator else 0.0
        fitted = [ybar + slope * (x - xbar) for x in xs]
        total = sum((y - ybar) ** 2 for y in ys)
        residual = sum((y - fit) ** 2 for y, fit in zip(ys, fitted))
        r2 = 1 - residual / total if total else 0.0
        return slope, max(0.0, min(1.0, r2))
