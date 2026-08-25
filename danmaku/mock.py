"""模拟弹幕源：后台线程定时生成弹幕，用于演示 / 学习 / 无抖音环境跑通。

数据随机从样例池抽取，用户也可自定。默认 2 秒一条。
"""
import random
import threading
import time

from core.events import DanmakuEvent
from danmaku.base import DanmakuProvider

# 内置样例弹幕：覆盖 L1（模板）、L2/L3（需要 AI）等多种场景
SAMPLE_DANMAKU = [
    "主播你好，第一次来",
    "这个多少钱？",
    "能便宜点吗？",
    "已关注，加油！",
    "主播今天状态不错",
    "有没有优惠券？",
    "谢谢主播的讲解",
    "这个适合新手吗？",
    "来了来了，前排围观",
    "主播给大家唱首歌呗",
]


class MockProvider(DanmakuProvider):
    def __init__(self, on_danmaku, samples=None, interval=2.0):
        super().__init__(on_danmaku)
        self.samples = samples if samples is not None else SAMPLE_DANMAKU
        self.interval = interval
        self._running = False
        self._thread = None

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        users = ["小明", "小红", "路人甲", "老王", "阿珍"]
        while self._running:
            event = DanmakuEvent(
                user=random.choice(users),
                content=random.choice(self.samples),
                timestamp=time.time(),
            )
            self.on_danmaku(event)
            time.sleep(self.interval)

    def stop(self):
        self._running = False
