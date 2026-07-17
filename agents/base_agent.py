from llm_client import OllamaClient


from llm_client import OllamaClient


class BaseAgent:
    name = ""

    def __init__(self, llm_client=None):
        self.llm_client = llm_client or OllamaClient()

    def read_memory(self, memory):
        return memory

    def call_tools(self, memory):
        return {}

    def reason(self, tool_results):
        return {}

    def llm_reason(self, system_prompt, user_payload, default_output):
        messages = [
            {
                "role": "system",
                "content": (
                    system_prompt
                    + "\n只返回合法 JSON，不要 markdown、不要代码块、不要额外解释。"
                ),
            },
            {
                "role": "user",
                "content": user_payload,
            },
        ]
        result = self.llm_client.chat_json(messages, default=default_output)
        return self._normalize_llm_output(result, default_output)

    def _normalize_llm_output(self, result, default_output):
        if not isinstance(result, dict):
            return default_output

        normalized = dict(result)
        key_map = {
            "risk_signal": "风险信号",
            "evidence": "证据",
            "abnormal": "异常",
            "knowledge": "知识",
        }
        for english_key, chinese_key in key_map.items():
            if english_key in normalized and chinese_key not in normalized:
                normalized[chinese_key] = normalized.pop(english_key)

        for key, value in default_output.items():
            normalized.setdefault(key, value)

        return normalized

    def write_memory(self, memory, output):
        memory["agent_outputs"][self.name] = output
        return memory

    def run(self, memory):
        tool_results = self.call_tools(memory)
        output = self.reason(tool_results)
        return self.write_memory(memory, output)
