"""本地 Ollama 引擎（Qwen3-4B），0 元/次，用标准库 urllib 调用。

对应省 token 阶梯的 L2：本地跑，不花钱。Ollama 未启动时调用会抛异常，
由上层 Coordinator 捕获后自动降级到 L3。
"""
import json
import urllib.request

from core.httputil import normalize_localhost


class LocalAI:
    def __init__(self, base_url="http://localhost:11434", model="qwen3:4b", timeout=60.0):
        # localhost → 127.0.0.1：规避 Windows 上 IPv6 优先导致的连接等待，
        # 服务未启动时能更快失败并降级（见 core/httputil.py）
        self.base_url = normalize_localhost(base_url).rstrip("/")
        self.model = model
        self.timeout = timeout

    def chat(self, messages):
        """调用 Ollama 的 /api/chat，返回 content 文本。失败抛异常由上层降级。"""
        payload = json.dumps({
            "model": self.model,
            "messages": messages,
            "stream": False,
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{self.base_url}/api/chat",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data["message"]["content"]

    def is_available(self):
        """探测 Ollama 是否在线（供 UI 状态条等使用）。"""
        try:
            with urllib.request.urlopen(f"{self.base_url}/api/tags", timeout=2.0):
                return True
        except Exception:
            return False
