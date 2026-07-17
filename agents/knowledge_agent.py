from agents.base_agent import BaseAgent

from agents.base_agent import BaseAgent


class KnowledgeAgent(BaseAgent):
    name = "知识Agent"

    def call_tools(self, memory):
        return memory["agent_outputs"]

    def reason(self, outputs):
        imaging = outputs.get("影像Agent", {})
        biomarker = outputs.get("生物标志物Agent", {})
        cognitive = outputs.get("认知Agent", {})

        knowledge_notes = [
            "淀粉样蛋白阳性可能早于认知下降出现",
        ]

        if imaging.get("异常") and not cognitive.get("异常", False):
            knowledge_notes.append("当病理阳性而认知仍正常时，需考虑前临床阿尔茨海默病模式")
        if biomarker.get("异常") and cognitive.get("异常", False):
            knowledge_notes.append("生物标志物和认知同时异常时，更支持症状期疾病风险")

        default_output = {
            "风险信号": "中",
            "知识": "；".join(knowledge_notes),
        }
        return self.llm_reason(
            system_prompt=(
                "你是阿尔茨海默病知识整合 Agent。"
                "请综合上游 Agent 输出，生成简洁中文知识结论。"
                "请使用中文键名：风险信号、知识。"
            ),
            user_payload=(
                f"影像输出: {imaging}\n"
                f"生物标志物输出: {biomarker}\n"
                f"认知输出: {cognitive}\n"
                f"全部上游输出: {outputs}\n"
                "请输出 JSON，键名使用：风险信号、知识。"
            ),
            default_output=default_output,
        )
