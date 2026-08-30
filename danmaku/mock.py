"""模拟弹幕源：后台线程定时生成弹幕，用于演示 / 学习 / 无抖音环境跑通。

数据随机从样例池抽取，用户也可自定。默认 2 秒一条。
支持 pause / resume：暂停后停止生成（手动发送的弹幕不受影响）。
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
    "什么时候发货？",
    "可以试用一下吗？",
    "这个和上一款有什么区别？",
    "主播声音真好听",
    "刚进来，这是在讲什么？",
    "支持主播！",
    "怎么下单呀？",
    "有没有小样赠送？",
    "666",
    "主播下次几点播？",
]


class MockProvider(DanmakuProvider):
    def __init__(self, on_danmaku, samples=None, interval=2.0):
        super().__init__(on_danmaku)
        self.samples = samples if samples is not None else SAMPLE_DANMAKU
        self.interval = interval
        self._running = False
        self._thread = None
        self._resumed = threading.Event()  # set=运行，clear=暂停
        self._resumed.set()

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def pause(self):
        """暂停生成（可在 UI 随时恢复）。"""
        self._resumed.clear()

    def resume(self):
        self._resumed.set()

    @property
    def paused(self):
        return not self._resumed.is_set()

    def _run(self):
        users = ["小明", "小红", "路人甲", "老王", "阿珍",
                 "阿强", "糖糖", "大白", "夜猫子", "奶茶"]
        while self._running:
            if not self._resumed.is_set():
                time.sleep(0.1)
                continue
            event = DanmakuEvent(
                user=random.choice(users),
                content=random.choice(self.samples),
                timestamp=time.time(),
            )
            self.on_danmaku(event)
            self._sleep(self.interval)

    def _sleep(self, seconds):
        """分段睡眠：保证 stop / pause 能及时响应，不卡半拍。"""
        end = time.time() + seconds
        while time.time() < end and self._running and self._resumed.is_set():
            time.sleep(0.05)

    def stop(self):
        self._running = False
        self._resumed.set()  # 唤醒可能在暂停中阻塞的循环，让它看到 _running=False
