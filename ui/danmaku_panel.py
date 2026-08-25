"""弹幕流面板：时间戳 + 彩色昵称 + 内容的滚动弹幕流。

用 tk.Text 而非 Listbox，是为了给不同用户昵称着色、时间用弱色，
视觉上更接近真实直播弹幕流。
"""
import time
import tkinter as tk
from tkinter import ttk

from ui import theme


class DanmakuPanel(ttk.Frame):
    def __init__(self, master):
        super().__init__(master, style="Card.TFrame")
        self._color_index = 0

        ttk.Label(self, text="弹幕流", style="Title.TLabel").pack(
            anchor="w", padx=10, pady=(8, 4))

        body = ttk.Frame(self, style="Card.TFrame")
        body.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        self.text = tk.Text(body, bg=theme.CARD, fg=theme.FG,
                            relief="flat", borderwidth=0, wrap="word",
                            font=theme.FONT_BODY, state="disabled",
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

    def append(self, event):
        """追加一条弹幕（已在主线程）。"""
        t = time.strftime("%H:%M:%S", time.localtime(event.timestamp))
        color_idx = self._color_index % len(theme.USER_COLORS)
        self._color_index += 1

        self.text.configure(state="normal")
        self.text.insert("end", f"[{t}] ", "time")
        self.text.insert("end", f"{event.user}：", f"user{color_idx}")
        self.text.insert("end", f"{event.content}\n", "content")
        self.text.configure(state="disabled")
        self.text.see("end")  # 自动滚到最新
