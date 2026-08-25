"""协调器（核心大脑）：聚合弹幕 + 三级阶梯调度 + 话题生成。

弹幕流：
  弹幕进来 → 进聚合窗口（攒满 N 条 或 满 M 秒）
           → 依次尝试 L1 模板 / L2 本地 / L3 云端
           → 产出 ReplySuggestion 通过 EventBus 发出去

话题生成：
  generate_topic() → 最近弹幕 + 知识库 → 本地/云端生成 → 返回话题文本

依赖注入：本地/云端 AI、模板、敏感词、知识库都由外部传入，
本模块不 import 任何具体实现，方便替换。
"""
import threading
import time
from collections import deque

from ai.prompts import (
    SYSTEM_PROMPT,
    TOPIC_SYSTEM_PROMPT,
    build_batch_prompt,
    build_topic_prompt,
)
from core.events import EVT_REPLY, EVT_LOG, ReplySuggestion


class Coordinator:
    def __init__(self, config, event_bus, budget, templates, sensitive,
                 local_ai, cloud_ai, kb):
        self.config = config
        self.event_bus = event_bus
        self.budget = budget
        self.templates = templates      # 模块（提供 match_template）
        self.sensitive = sensitive      # 模块（提供 filter_text）
        self.local_ai = local_ai        # LocalAI 或 None
        self.cloud_ai = cloud_ai        # CloudAI 或 None
        self.kb = kb                    # 知识库（供话题生成检索）

        agg = config.get("aggregate", {})
        self.max_count = agg.get("count", 5)       # 聚合条数阈值
        self.max_seconds = agg.get("seconds", 20)  # 聚合时间阈值（秒）

        self._buffer = []               # 当前聚合中的弹幕
        self._recent = deque(maxlen=50)  # 最近弹幕，供话题生成取素材
        self._lock = threading.Lock()   # 弹幕来自后台线程，需加锁
        self._timer = None              # 定时刷新定时器
        self._local_ok = True           # 本地 AI 可用性缓存（乐观，首次会尝试）
        self._local_retry_at = 0.0      # 下次重试本地 AI 的时间戳

    # ---------- 弹幕入口与聚合 ----------

    def on_danmaku(self, event):
        """弹幕入口：入聚合窗口，同时缓存到最近弹幕，攒够条数立即处理。"""
        with self._lock:
            self._recent.append(event)
            self._buffer.append(event)
            if len(self._buffer) >= self.max_count:
                self._flush()

    def start(self):
        """启动聚合定时器。"""
        self._schedule()

    def stop(self):
        """停止定时器。"""
        if self._timer:
            self._timer.cancel()
            self._timer = None

    def _schedule(self):
        """安排下一次定时刷新。"""
        self._timer = threading.Timer(self.max_seconds, self._on_timeout)
        self._timer.daemon = True
        self._timer.start()

    def _on_timeout(self):
        """到点仍未攒满条数，也把已有弹幕处理掉。"""
        with self._lock:
            if self._buffer:
                self._flush()
        self._schedule()

    # ---------- 三级阶梯 ----------

    def _flush(self):
        """处理当前聚合的一批弹幕。"""
        batch = self._buffer
        self._buffer = []
        # 敏感词过滤后再进入 AI / 模板判断
        contents = [self.sensitive.filter_text(e.content) for e in batch]

        suggestion = (
            self._try_l1_template(contents)
            or self._try_l2_local(contents)
            or self._try_l3_cloud(contents)
        )
        # 三级都没产出 → 兜底，避免界面空着
        if suggestion is None:
            suggestion = ReplySuggestion(
                content="（暂无建议，可忽略这批弹幕）",
                source="fallback",
                matched=contents,
            )

        self.event_bus.publish(EVT_REPLY, suggestion)
        self._log(f"回复建议[{suggestion.source}]：{suggestion.content}")

    def _try_l1_template(self, contents):
        """L1：模板命中，0 token / 0 元，优先秒回。"""
        for c in contents:
            reply = self.templates.match_template(c)
            if reply:
                return ReplySuggestion(content=reply, source="template", matched=[c])
        return None

    def _try_l2_local(self, contents):
        """L2：本地 Ollama 生成，0 元；失败/未启用则返回 None 走 L3。

        带可用性缓存：连接失败后 60 秒内跳过 L2，避免反复连接刷屏；
        到期自动重试，Ollama 启动后恢复。
        """
        if not self.local_ai:
            return None
        if not self._local_ok and time.time() < self._local_retry_at:
            return None
        try:
            text = self.local_ai.chat(self._build_messages(contents))
            self._local_ok = True   # 成功，恢复可用
            return ReplySuggestion(content=text, source="local", matched=contents)
        except Exception as e:
            if self._local_ok:      # 只在「可用→不可用」的首次失败时提示一次
                self._log(
                    "本地 AI（Ollama）不可用，已暂停本地回复，60 秒后自动重试。"
                    f"请确认已启动 Ollama。（原因：{e}）"
                )
            self._local_ok = False
            self._local_retry_at = time.time() + 60
            return None

    def _try_l3_cloud(self, contents):
        """L3：云端 DeepSeek 批量生成，先过预算检查；超限则返回 None。"""
        if not self.cloud_ai or not self.budget.can_call_cloud():
            return None
        try:
            text = self.cloud_ai.chat(self._build_messages(contents))
            self.budget.record_call(cost=0.01)  # 估算单次费用，可据实调整
            return ReplySuggestion(content=text, source="cloud", cost=0.01, matched=contents)
        except Exception as e:
            self._log(f"云端 AI 失败：{e}")
            return None

    # ---------- 话题生成 ----------

    def generate_topic(self):
        """基于最近弹幕 + 知识库生成一个聊天话题。

        阻塞式调用（AI 可能耗时数秒），请在后台线程调用。
        优先走本地（0 元），失败走云端（预算内）；都不可用返回 None。
        """
        with self._lock:
            recent = [e.content for e in self._recent]
        kb_texts = self._kb_context(recent)

        # 既没弹幕也没知识，无从谈起
        if not recent and not kb_texts:
            return None

        messages = [
            {"role": "system", "content": TOPIC_SYSTEM_PROMPT},
            {"role": "user", "content": build_topic_prompt(recent, kb_texts)},
        ]

        if self.local_ai and self._local_ok:
            try:
                return self.local_ai.chat(messages)
            except Exception as e:
                self._local_ok = False
                self._local_retry_at = time.time() + 60
                self._log(f"话题生成：本地 AI 不可用（{e}）")

        if self.cloud_ai and self.budget.can_call_cloud():
            try:
                text = self.cloud_ai.chat(messages)
                self.budget.record_call(cost=0.01)
                return text
            except Exception as e:
                self._log(f"话题生成：云端 AI 失败（{e}）")

        return None

    def _kb_context(self, recent, top_k=3):
        """从知识库取与最近弹幕相关的内容，作为话题素材。

        优先用最近弹幕做语义检索；检索不到或知识库不支持时，
        回退到全量列表的前几条。
        """
        if not self.kb:
            return []
        query = " ".join(recent[-3:]) if recent else ""
        hits = []
        try:
            if query:
                hits = self.kb.search(query, top_k=top_k)
        except Exception as e:
            self._log(f"知识库检索失败：{e}")
        if not hits:
            try:
                hits = self.kb.list_all()[:top_k]
            except Exception as e:
                self._log(f"知识库读取失败：{e}")
        return [h["text"] for h in hits]

    # ---------- 工具 ----------

    def _build_messages(self, contents):
        """把一批弹幕组装成统一的 messages 结构（本地/云端通用）。"""
        return [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_batch_prompt(contents)},
        ]

    def _log(self, msg):
        self.event_bus.publish(EVT_LOG, msg)
