"""弹幕源抽象基类。

所有弹幕源（模拟 / 抖音 / 其他平台）都实现 start / stop，
并通过构造时传入的 on_danmaku 回调往外吐 DanmakuEvent。
这样上层（main.py / Coordinator）只依赖这个抽象，不关心具体来源。
"""
from abc import ABC, abstractmethod


class DanmakuProvider(ABC):
    def __init__(self, on_danmaku):
        # on_danmaku: Callable[[DanmakuEvent], None]
        self.on_danmaku = on_danmaku

    @abstractmethod
    def start(self):
        """开始拉取弹幕，产生事件时回调 on_danmaku。"""

    @abstractmethod
    def stop(self):
        """停止拉取，释放资源。"""
