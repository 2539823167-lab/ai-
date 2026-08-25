"""入口：加载配置 → 组装各模块（依赖注入）→ 启动 UI。

这里是唯一「知道所有具体实现」的地方：把各能力模块按依赖关系装配起来，
核心逻辑（Coordinator）只依赖抽象，不在代码里 import 具体实现。
"""
import json
import os

from ai.cloud import CloudAI
from ai.local import LocalAI
from core.budget import BudgetGuard
from core.coordinator import Coordinator
from core.events import EventBus, EVT_DANMAKU, EVT_LOG
from danmaku.mock import MockProvider
from kb.store import SimpleKB
from rules import sensitive, templates


def load_config():
    """读取 config.json。"""
    path = os.path.join(os.path.dirname(__file__), "config.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_ai(config):
    """按配置装配本地/云端 AI；未启用则返回 None，由 Coordinator 自动降级。

    云端 API key 优先读环境变量 DEEPSEEK_API_KEY，避免明文写进 config.json。
    """
    local_cfg = config["ai"]["local"]
    cloud_cfg = config["ai"]["cloud"]

    local_ai = None
    if local_cfg.get("enabled"):
        local_ai = LocalAI(local_cfg["base_url"], local_cfg["model"])

    cloud_ai = None
    # API key 优先级：环境变量 DEEPSEEK_API_KEY > config.json 的 api_key
    api_key = os.environ.get("DEEPSEEK_API_KEY", "") or cloud_cfg.get("api_key", "")
    if cloud_cfg.get("enabled") and api_key:
        cloud_ai = CloudAI(api_key, cloud_cfg["model"], cloud_cfg["base_url"])

    return local_ai, cloud_ai


def build_kb(config):
    """按配置装配知识库，默认 SimpleKB；backend=chroma 时启用语义检索。"""
    kb_cfg = config.get("kb", {})
    if kb_cfg.get("backend") == "chroma":
        from kb.store import ChromaKB
        return ChromaKB(
            collection=kb_cfg.get("collection", "live_kb"),
            persist_dir=kb_cfg.get("persist_dir", "./chroma_data"),
            embedding=kb_cfg.get("embedding", "ollama"),
            embedding_url=kb_cfg.get("embedding_url", "http://localhost:11434"),
            embedding_model=kb_cfg.get("embedding_model", "bge-m3"),
        )
    return SimpleKB()


def build_provider(config, on_danmaku):
    """按配置装配弹幕源：mock（默认）或 douyin（接入脚手架）。

    douyin 目前是脚手架（签名 / WebSocket / protobuf 待接入），
    切换后需按《danmaku/抖音接入说明.md》补全才能真正抓到弹幕。
    """
    provider_cfg = config.get("danmaku", {})
    name = provider_cfg.get("provider", "mock")
    if name == "douyin":
        from danmaku.douyin import DouyinProvider
        return DouyinProvider(
            on_danmaku,
            live_url=provider_cfg.get("live_url") or None,
            room_id=provider_cfg.get("room_id") or None,
        )
    return MockProvider(on_danmaku, interval=provider_cfg.get("mock_interval", 2.0))


def main():
    config = load_config()
    event_bus = EventBus()

    # 日志直接打到控制台，方便调试观察三级阶梯走向
    event_bus.subscribe(EVT_LOG, lambda msg: print(f"[日志] {msg}"))

    budget = BudgetGuard(config["budget"]["max_calls"], config["budget"]["max_cost"])
    kb = build_kb(config)
    local_ai, cloud_ai = build_ai(config)

    coordinator = Coordinator(
        config=config,
        event_bus=event_bus,
        budget=budget,
        templates=templates,
        sensitive=sensitive,
        local_ai=local_ai,
        cloud_ai=cloud_ai,
        kb=kb,
    )

    # 弹幕源：按 config 的 danmaku.provider 选择 mock 或 douyin
    def on_danmaku(event):
        event_bus.publish(EVT_DANMAKU, event)   # 通知 UI 显示
        coordinator.on_danmaku(event)           # 交给协调器聚合判断

    provider = build_provider(config, on_danmaku)

    from ui.app import App
    app = App(config, event_bus, coordinator, provider, kb)
    app.mainloop()


if __name__ == "__main__":
    main()
