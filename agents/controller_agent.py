from agents.base_agent import BaseAgent

from agents.base_agent import BaseAgent


class ControllerAgent(BaseAgent):
    name = "控制器"

    def run(self, memory):
        outputs = memory["agent_outputs"]

        score_map = {"低": 0, "中": 1, "高": 2}
        score_breakdown = {
            agent_name: score_map.get(agent_output.get("风险信号", "低"), 0)
            for agent_name, agent_output in outputs.items()
        }
        average_score = sum(score_breakdown.values()) / max(len(score_breakdown), 1)

        conflicts = self._detect_conflicts(outputs)
        memory["conflicts"] = conflicts

        risk = "高" if average_score > 1 else "中" if average_score > 0.5 else "低"
        summary = self._build_summary(outputs, conflicts, risk)

        memory["controller_output"] = {
            "评分明细": score_breakdown,
            "平均分": average_score,
            "冲突": conflicts,
            "风险等级": risk,
        }
        memory["final_report"] = {
            "风险等级": risk,
            "冲突": conflicts,
            "总结": summary,
        }
        return memory

    def _detect_conflicts(self, outputs):
        conflicts = []

        imaging = outputs.get("影像Agent", {})
        cognitive = outputs.get("认知Agent", {})

        if imaging.get("异常") and not cognitive.get("异常", False):
            conflicts.append("病理-认知不一致")

        return conflicts

    def _build_summary(self, outputs, conflicts, risk):
        imaging = outputs.get("影像Agent", {})
        biomarker = outputs.get("生物标志物Agent", {})
        cognitive = outputs.get("认知Agent", {})
        followup = outputs.get("随访Agent", {})

        pieces = [
            f"综合风险等级为{risk}。",
            f"影像信号：{imaging.get('风险信号', '未知')}。",
            f"生物标志物信号：{biomarker.get('风险信号', '未知')}。",
            f"认知信号：{cognitive.get('风险信号', '未知')}。",
            f"随访信号：{followup.get('风险信号', '未知')}。",
        ]

        if conflicts:
            pieces.append("检测到冲突：" + "，".join(conflicts) + "。")
            if "病理-认知不一致" in conflicts:
                pieces.append("该模式提示可能处于前临床阿尔茨海默病阶段。")

        return " ".join(pieces)
