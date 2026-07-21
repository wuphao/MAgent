import json
import re
import time
import urllib.error
import urllib.request

from config import (
    DEEPSEEK_API_KEY,
    DEEPSEEK_BASE_URL,
    DEEPSEEK_MODEL,
    DEEPSEEK_TIMEOUT_SECONDS,
)


class DeepSeekClient:
    def __init__(
        self,
        api_key=DEEPSEEK_API_KEY,
        base_url=DEEPSEEK_BASE_URL,
        model=DEEPSEEK_MODEL,
        timeout_seconds=DEEPSEEK_TIMEOUT_SECONDS,
    ):
        self.api_key = api_key.strip()
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds

    def chat(self, messages, temperature=0.0, num_predict=256):
        if not self.api_key:
            raise RuntimeError(
                "未配置 DEEPSEEK_API_KEY。请先设置环境变量后再启用大模型。"
            )
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "temperature": temperature,
            "max_tokens": num_predict,
            "response_format": {"type": "json_object"},
            "thinking": {"type": "disabled"},
        }

        data = json.dumps(payload).encode("utf-8")
        last_error = None
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=data,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        for attempt in range(3):
            try:
                with urllib.request.urlopen(
                    request, timeout=self.timeout_seconds
                ) as response:
                    body = response.read().decode("utf-8")
                parsed = json.loads(body)
                return parsed["choices"][0]["message"]["content"]
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="replace")
                last_error = f"HTTP {exc.code}: {detail}"
                if exc.code in (400, 401, 402, 403):
                    break
                if attempt < 2:
                    time.sleep(1.5 * (attempt + 1))
            except (urllib.error.URLError, TimeoutError, ConnectionError, KeyError, json.JSONDecodeError) as exc:
                last_error = exc
                if attempt < 2:
                    time.sleep(1.5 * (attempt + 1))

        raise RuntimeError(
            f"无法调用 DeepSeek（地址：{self.base_url}，模型：{self.model}）：{last_error}"
        )

    def chat_json(self, messages, temperature=0.0, default=None, num_predict=256):
        try:
            content = self.chat(
                messages,
                temperature=temperature,
                num_predict=num_predict,
            )
        except Exception:
            if default is not None:
                return default
            raise
        return self._extract_json(content, default=default)

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
