"""弹幕流面板：时间戳 + 彩色昵称 + 内容的滚动弹幕流。

在展示之外提供两个实时交互入口：
  - 底部输入框手动发送弹幕（回车即进入 AI 处理管线，高亮区分）；
  - 主播采纳建议后「上屏」，在流里显示一条主播消息，形成闭环。

滚动做了智能处理：用户上翻查看历史时不打扰，回到底部后恢复自动跟随。
"""
import time
import tkinter as tk
from tkinter import ttk

from ui import theme


class DanmakuPanel(theme.Card):
    def __init__(self, master, on_send=None, on_clear=None):
        super().__init__(master)
        self.on_send = on_send
        self._color_index = 0
        self._count = 0

        # ---- 标题行：弹幕流 · 计数 · 清空 ----
        header = tk.Frame(self, bg=theme.CARD)
        header.pack(fill="x", padx=10, pady=(8, 4))
        ttk.Label(header, text="💬 弹幕流", style="Title.TLabel").pack(side="left")
        self.count_label = ttk.Label(header, text="共 0 条", style="Muted.TLabel")
        self.count_label.pack(side="left", padx=(8, 0))
        if on_clear:
            ttk.Button(header, text="清空", style="Tool.TButton",
                       command=on_clear).pack(side="right")

        # ---- 弹幕文本区 ----
        body = tk.Frame(self, bg=theme.CARD)
        body.pack(fill="both", expand=True, padx=8, pady=(0, 6))

        self.text = tk.Text(body, bg=theme.CARD, fg=theme.FG,
                            relief="flat", borderwidth=0, wrap="word",
                            font=theme.FONT_BODY, state="disabled", height=6,
                            padx=10, pady=6, highlightthickness=0,
                            cursor="arrow")
        self.text.pack(side="left", fill="both", expand=True)

        scrollbar = ttk.Scrollbar(body, orient="vertical",
                                  style="Vertical.TScrollbar", command=self.text.yview)
        scrollbar.pack(side="right", fill="y")
        self.text.configure(yscrollcommand=scrollbar.set)

        # 预定义 tag：时间弱色、内容主色、各用户昵称颜色
        self.text.tag_configure("time", foreground=theme.MUTED)
        self.text.tag_configure("content", foreground=theme.FG)
        for i, c in enumerate(theme.USER_COLORS):
            self.text.tag_configure(f"user{i}", foreground=c)
        # 手动发送 / 主播上屏的专用配色
        self.text.tag_configure("manual_user", foreground=theme.ACCENT,
                                font=(theme.FONT_FAMILY, 10, "bold"))
        self.text.tag_configure("manual_content", foreground="#B3E5FC")
        self.text.tag_configure("host_time", foreground=theme.MUTED)
        self.text.tag_configure("host_name", foreground=theme.SUCCESS,
                                font=(theme.FONT_FAMILY, 10, "bold"))
        self.text.tag_configure("host_content", foreground="#C8E6C9")

        # ---- 手动发送行 ----
        row = tk.Frame(self, bg=theme.CARD)
        row.pack(fill="x", padx=8, pady=(0, 8))
        self.entry = theme.PlaceholderEntry(
            row, placeholder="输入弹幕，回车模拟观众发言…")
        self.entry.pack(side="left", fill="x", expand=True)
        self.entry.bind("<Return>", lambda _e: self._send())
        ttk.Button(row, text="发送", style="Accent.TButton", width=8,
                   command=self._send).pack(side="left", padx=(6, 0))

    # ---------- 展示 ----------

    def append(self, event):
        """追加一条弹幕（已在主线程）。"""
        stick = self._at_bottom()
        t = time.strftime("%H:%M:%S", time.localtime(event.timestamp))
        color_idx = self._color_index % len(theme.USER_COLORS)
        self._color_index += 1
        self._count += 1
        self.count_label.configure(text=f"共 {self._count} 条")

        self.text.configure(state="normal")
        self.text.insert("end", f"[{t}] ", "time")
        if getattr(event, "manual", False):
            # 手动发送的弹幕：青蓝高亮，一眼区分
            self.text.insert("end", f"🙋 {event.user}：", "manual_user")
            self.text.insert("end", f"{event.content}\n", "manual_content")
        else:
            self.text.insert("end", f"{event.user}：", f"user{color_idx}")
            self.text.insert("end", f"{event.content}\n", "content")
        self.text.configure(state="disabled")
        if stick:
            self.text.see("end")  # 只有原本就在底部才自动跟随

    def append_host(self, content):
        """主播采纳建议后上屏，在流里显示一条主播消息。"""
        stick = self._at_bottom()
        t = time.strftime("%H:%M:%S")
        self._count += 1
        self.count_label.configure(text=f"共 {self._count} 条")

        self.text.configure(state="normal")
        self.text.insert("end", f"[{t}] ", "host_time")
        self.text.insert("end", "📤 主播：", "host_name")
        self.text.insert("end", f"{content}\n", "host_content")
        self.text.configure(state="disabled")
        if stick:
            self.text.see("end")

    def clear(self):
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.configure(state="disabled")
        self._count = 0
        self.count_label.configure(text="共 0 条")

    # ---------- 内部 ----------

    def _at_bottom(self):
        """滚动条是否已在最底部（决定追加后要不要自动跟随）。"""
        return self.text.yview()[1] >= 0.999

    def _send(self):
        """把输入框内容作为一条弹幕送出（回调由 App 接入处理管线）。"""
        content = self.entry.get().strip()
        if not content:
            return
        self.entry.clear()
        self.entry.focus_set()
        if self.on_send:
            self.on_send(content)
