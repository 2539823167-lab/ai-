"""回复建议面板：来源徽章 + 最新建议卡片 + 可回看的历史列表。

实时交互：
  - ⚡ 立即处理：不等聚合窗口攒满，马上处理已有弹幕；
  - 聚合窗口在线调节：攒 N 条 / M 秒，改完即生效；
  - 一键复制 / 采纳上屏：把建议文案复制并标记为主播回复。
"""
import time
import tkinter as tk
from tkinter import ttk

from ui import theme

# 来源 → 中文名
SOURCE_NAMES = {
    "template": "模板秒回",
    "local": "本地AI",
    "cloud": "云端AI",
    "fallback": "兜底",
}

HISTORY_LIMIT = 100  # 历史建议最多保留条数


class ReplyPanel(theme.Card):
    def __init__(self, master, on_flush=None, on_adopt=None,
                 on_aggregate=None, init_count=5, init_seconds=20):
        super().__init__(master)
        self.on_adopt = on_adopt
        self._history = []      # [(ReplySuggestion, "HH:MM:SS")]，新的在前
        self._latest = None

        # ---- 标题行 + 聚合窗口调节 ----
        header = tk.Frame(self, bg=theme.CARD)
        header.pack(fill="x", padx=10, pady=(8, 2))
        ttk.Label(header, text="💡 回复建议", style="Title.TLabel").pack(side="left")

        if on_flush:
            ttk.Button(header, text="⚡ 立即处理", style="Tool.TButton",
                       command=on_flush).pack(side="right")
        if on_aggregate:
            agg = tk.Frame(header, bg=theme.CARD)
            agg.pack(side="right", padx=(0, 6))
            ttk.Label(agg, text="攒", style="Muted.TLabel").pack(side="left")
            self.count_var = tk.StringVar(value=str(init_count))
            sp_count = ttk.Spinbox(agg, from_=1, to=99, width=3,
                                   textvariable=self.count_var)
            sp_count.pack(side="left", padx=2)
            ttk.Label(agg, text="条 /", style="Muted.TLabel").pack(side="left")
            self.seconds_var = tk.StringVar(value=str(init_seconds))
            sp_seconds = ttk.Spinbox(agg, from_=5, to=300, width=4, increment=5,
                                     textvariable=self.seconds_var)
            sp_seconds.pack(side="left", padx=2)
            ttk.Label(agg, text="秒", style="Muted.TLabel").pack(side="left")
            for sp in (sp_count, sp_seconds):
                sp.configure(command=self._emit_aggregate)
                sp.bind("<Return>", lambda _e: self._emit_aggregate())
                sp.bind("<FocusOut>", lambda _e: self._emit_aggregate())
            self._on_aggregate = on_aggregate

        # ---- 最新建议卡片 ----
        meta = tk.Frame(self, bg=theme.CARD)
        meta.pack(fill="x", padx=10, pady=(4, 0))
        self.pill = tk.Label(meta, text="等待弹幕…", bg=theme.CARD_ALT, fg=theme.MUTED,
                             font=(theme.FONT_FAMILY, 9, "bold"), padx=10, pady=2)
        self.pill.pack(side="left")
        self.meta_label = ttk.Label(meta, text="", style="Muted.TLabel")
        self.meta_label.pack(side="right")

        self.content = tk.Text(self, bg=theme.CARD_ALT, fg=theme.FG,
                               relief="flat", borderwidth=0, wrap="word",
                               font=(theme.FONT_FAMILY, 12), height=4,
                               padx=12, pady=10, highlightthickness=0,
                               state="disabled")
        self.content.pack(fill="x", padx=8, pady=(6, 0))

        self.matched_label = ttk.Label(self, text="", style="Muted.TLabel",
                                       wraplength=430, justify="left")
        self.matched_label.pack(anchor="w", padx=12, pady=(4, 0))

        btns = tk.Frame(self, bg=theme.CARD)
        btns.pack(fill="x", padx=10, pady=(6, 2))
        self.copy_btn = ttk.Button(btns, text="📋 复制", style="Tool.TButton",
                                   command=self._copy)
        self.copy_btn.pack(side="right")
        if on_adopt:
            ttk.Button(btns, text="✅ 采纳上屏", style="Accent.TButton",
                       command=self._adopt).pack(side="right", padx=(0, 6))

        # ---- 历史建议（点击回看）----
        ttk.Label(self, text="历史建议（点击回看）", style="Muted.TLabel").pack(
            anchor="w", padx=12, pady=(2, 0))
        hist_body = tk.Frame(self, bg=theme.CARD)
        hist_body.pack(fill="both", expand=True, padx=8, pady=(2, 8))
        self.hist = tk.Text(hist_body, bg=theme.CARD, fg=theme.FG,
                            relief="flat", borderwidth=0, wrap="word",
                            font=theme.FONT_SMALL, padx=8, pady=2, height=4,
                            highlightthickness=0, state="disabled", cursor="hand2")
        self.hist.pack(side="left", fill="both", expand=True)
        hist_scroll = ttk.Scrollbar(hist_body, orient="vertical",
                                    style="Vertical.TScrollbar",
                                    command=self.hist.yview)
        hist_scroll.pack(side="right", fill="y")
        self.hist.configure(yscrollcommand=hist_scroll.set)
        self.hist.tag_configure("empty", foreground=theme.MUTED)

    # ---------- 展示 ----------

    def show(self, suggestion, remember=True):
        """展示一条回复建议（已在主线程），来源徽章按类型着色。"""
        now = time.strftime("%H:%M:%S")
        self._latest = suggestion

        name = SOURCE_NAMES.get(suggestion.source, suggestion.source)
        color = theme.SOURCE_COLORS.get(suggestion.source, theme.MUTED)
        pill_fg = "#0D1B26" if suggestion.source != "fallback" else theme.FG
        self.pill.configure(text=name, bg=color, fg=pill_fg)

        cost_txt = f"约 ¥{suggestion.cost:.3f}" if suggestion.cost else "0 元"
        self.meta_label.configure(text=f"{now} · 成本 {cost_txt}")

        self.content.configure(state="normal")
        self.content.delete("1.0", "end")
        self.content.insert("1.0", suggestion.content)
        self.content.configure(state="disabled")

        matched = " ｜ ".join(suggestion.matched[:3]) if suggestion.matched else "—"
        self.matched_label.configure(text=f"针对弹幕：{matched[:90]}")

        if remember:
            self._history.insert(0, (suggestion, now))
            if len(self._history) > HISTORY_LIMIT:
                self._history.pop()
            self._render_history()

    # ---------- 内部 ----------

    def _render_history(self):
        """按当前历史列表整块重绘（行数有限，重绘比维护 tag 位移更稳）。"""
        self.hist.configure(state="normal")
        self.hist.delete("1.0", "end")
        if not self._history:
            self.hist.insert("end", "暂无历史建议", "empty")
        for i, (sug, ts) in enumerate(self._history):
            name = SOURCE_NAMES.get(sug.source, sug.source)
            tag = f"h{i}"
            self.hist.insert("end", f"{ts} · {name} · {sug.content[:60]}\n", tag)
            self.hist.tag_configure(
                tag, foreground=theme.SOURCE_COLORS.get(sug.source, theme.FG))
            self.hist.tag_bind(
                tag, "<Button-1>", lambda _e, idx=i: self._recall(idx))
        self.hist.configure(state="disabled")

    def _recall(self, idx):
        """点击历史条目回看该建议（不重复入历史）。"""
        if 0 <= idx < len(self._history):
            self.show(self._history[idx][0], remember=False)

    def _emit_aggregate(self):
        """把聚合窗口调节回调给 App（改成即生效）。"""
        cb = getattr(self, "_on_aggregate", None)
        if cb:
            cb(self.count_var.get(), self.seconds_var.get())

    def _copy(self):
        """把建议文案复制到剪贴板，按钮短暂反馈「已复制」。"""
        text = self.content.get("1.0", "end").strip()
        if not text:
            return
        self.clipboard_clear()
        self.clipboard_append(text)
        self.copy_btn.configure(text="✓ 已复制")
        self.after(1200, lambda: self.copy_btn.configure(text="📋 复制"))

    def _adopt(self):
        """采纳当前建议：交给 App 复制 + 弹幕流上屏。"""
        text = self.content.get("1.0", "end").strip()
        if text and self.on_adopt:
            self.on_adopt(text)
