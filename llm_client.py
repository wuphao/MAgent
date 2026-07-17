import json
import json
import re
import time
import urllib.error
import urllib.request

from config import OLLAMA_BASE_URL, OLLAMA_MODEL, OLLAMA_TIMEOUT_SECONDS


class OllamaClient:
    def __init__(
        self,
        base_url=OLLAMA_BASE_URL,
        model=OLLAMA_MODEL,
        timeout_seconds=OLLAMA_TIMEOUT_SECONDS,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds

    def chat(self, messages, temperature=0.0):
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "format": "json",
            "options": {
                "temperature": temperature,
                "num_predict": 256,
            },
        }

        data = json.dumps(payload).encode("utf-8")
        last_error = None
        for base_url in self._candidate_base_urls():
            request = urllib.request.Request(
                f"{base_url}/api/chat",
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )

            for attempt in range(3):
                try:
                    with urllib.request.urlopen(
                        request, timeout=self.timeout_seconds
                    ) as response:
                        body = response.read().decode("utf-8")
                    parsed = json.loads(body)
                    return parsed["message"]["content"]
                except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
                    last_error = exc
                    if attempt < 2:
                        time.sleep(1.5 * (attempt + 1))

        raise RuntimeError(
            f"无法调用 Ollama（地址：{self.base_url}，模型：{self.model}）：{last_error}"
        )

    def chat_json(self, messages, temperature=0.0, default=None):
        try:
            content = self.chat(messages, temperature=temperature)
        except Exception:
            if default is not None:
                return default
            raise
        return self._extract_json(content, default=default)

    def _candidate_base_urls(self):
        candidates = [self.base_url]
        fallback = "http://localhost:11434"
        if fallback not in candidates:
            candidates.append(fallback)
        return candidates

    def _extract_json(self, text, default=None):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass

        if default is not None:
            return default
        raise ValueError(f"模型返回内容不是合法 JSON：{text}")
