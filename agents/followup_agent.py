from agents.base_agent import BaseAgent
from agents.base_agent import BaseAgent
from tools.followup_tool import FollowUpTool


class FollowUpAgent(BaseAgent):
    name = "随访Agent"

    def call_tools(self, memory):
        result = FollowUpTool().run(memory["raw_inputs"]["follow_up"])
        memory["tool_results"]["followup"] = result
        return result

    def reason(self, result):
        abnormal = result["trend"] != "稳定"
        default_output = {
            "风险信号": "中" if abnormal else "低",
            "证据": [f"随访结果={result}"],
            "异常": abnormal,
        }
        return self.llm_reason(
            system_prompt=(
                "你是阿尔茨海默病随访轨迹分析 Agent。"
                "请根据随访变化给出中文、结构化判断。"
                "请使用中文键名：风险信号、证据、异常。"
            ),
            user_payload=(
                f"随访结果: {result}\n"
                "请输出 JSON，键名使用：风险信号、证据、异常。"
            ),
            default_output=default_output,
        )
