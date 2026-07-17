from agents.base_agent import BaseAgent
from agents.base_agent import BaseAgent
from tools.cognitive_tool import CognitiveTool


class CognitiveAgent(BaseAgent):
    name = "认知Agent"

    def call_tools(self, memory):
        result = CognitiveTool().run(memory["raw_inputs"]["cognitive_scores"])
        memory["tool_results"]["cognitive"] = result
        return result

    def reason(self, result):
        abnormal = result["level"] != "正常"
        default_output = {
            "风险信号": "低" if result["level"] == "正常" else "高",
            "证据": [f"认知评估结果={result}"],
            "异常": abnormal,
        }
        return self.llm_reason(
            system_prompt=(
                "你是阿尔茨海默病认知评估 Agent。"
                "请根据 MMSE 结果给出中文、结构化判断。"
                "请使用中文键名：风险信号、证据、异常。"
            ),
            user_payload=(
                f"认知评估结果: {result}\n"
                "请输出 JSON，键名使用：风险信号、证据、异常。"
            ),
            default_output=default_output,
        )
