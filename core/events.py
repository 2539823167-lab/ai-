"""数据模型与事件总线（零依赖，仅标准库）。

本模块是全项目的「通用语言」：弹幕、回复建议都先转成这里的数据类，
模块之间通过 EventBus 解耦，谁都不需要 import 谁的具体实现。
"""
from dataclasses import dataclass, field

# 事件类型常量（避免散落魔法字符串）
EVT_DANMAKU = "danmaku"   # 新弹幕到达
EVT_REPLY = "reply"       # 产生一条回复建议
EVT_LOG = "log"           # 日志


@dataclass
class DanmakuEvent:
    """一条弹幕。"""
    user: str              # 用户名
    content: str           # 弹幕内容
    timestamp: float       # 时间戳（time.time()）


@dataclass
class ReplySuggestion:
    """一条回复建议。"""
    content: str                              # 建议回复的文案
    source: str = "template"                  # template / local / cloud / fallback
    cost: float = 0.0                         # 本次估算费用（元）
    matched: list = field(default_factory=list)  # 命中的弹幕内容列表


class EventBus:
    """极简事件总线：按事件类型维护回调列表，publish 时依次调用。"""

    def __init__(self):
        self._handlers = {}

    def subscribe(self, event_type, handler):
        """订阅某类事件。handler 接收一个参数 data。"""
        self._handlers.setdefault(event_type, []).append(handler)

    def publish(self, event_type, data):
        """发布事件。单个 handler 抛异常不影响其他 handler。"""
        for handler in self._handlers.get(event_type, []):
            try:
                handler(data)
            except Exception as e:  # 兜底，避免某个订阅者拖垮整条链路
                print(f"[EventBus] {event_type} 的订阅者出错: {e}")
