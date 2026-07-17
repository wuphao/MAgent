from agents.base_agent import BaseAgent
from agents.base_agent import BaseAgent
from tools.biomarker_tool import BiomarkerTool


class BiomarkerAgent(BaseAgent):
    name = "生物标志物Agent"

    def call_tools(self, memory):
        result = BiomarkerTool().run(memory["raw_inputs"]["biomarkers"])
        memory["tool_results"]["biomarkers"] = result
        return result

    def reason(self, result):
        abnormal = result["abeta_status"] == "偏低" or result["ptau_status"] == "升高"
        default_output = {
            "风险信号": "高" if abnormal else "低",
            "证据": [f"生物标志物结果={result}"],
            "异常": abnormal,
        }
        return self.llm_reason(
            system_prompt=(
                "你是阿尔茨海默病生物标志物分析 Agent。"
                "请根据生物标志物结果给出中文、结构化判断。"
                "请使用中文键名：风险信号、证据、异常。"
            ),
            user_payload=(
                f"生物标志物结果: {result}\n"
                "请输出 JSON，键名使用：风险信号、证据、异常。"
            ),
            default_output=default_output,
        )
