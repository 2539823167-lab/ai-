"""云端 DeepSeek（deepseek-chat），OpenAI 兼容接口，用标准库 urllib 调用。

对应省 token 阶梯的 L3：批量生成、按量计费，由 BudgetGuard 控制调用次数。
"""
import json
import urllib.request

from core.httputil import normalize_localhost


class CloudAI:
    def __init__(self, api_key, model="deepseek-chat",
                 base_url="https://api.deepseek.com", timeout=60.0):
        self.api_key = api_key
        self.model = model
        # 兼容自建代理把地址配成 localhost 的情况（规范化后再拼接接口路径）
        self.base_url = normalize_localhost(base_url).rstrip("/")
        self.timeout = timeout

    def chat(self, messages):
        """调用 /chat/completions，返回 choices[0].message.content。失败抛异常由上层降级。"""
        payload = json.dumps({
            "model": self.model,
            "messages": messages,
            "stream": False,
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data["choices"][0]["message"]["content"]
