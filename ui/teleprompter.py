"""提词器面板：大字口播词 + 自动滚动（可调速）+ 字号调节 + 话题生成。"""
import tkinter as tk
from tkinter import ttk

from ui import theme


class TeleprompterPanel(theme.Card):
    def __init__(self, master, on_generate=None):
        super().__init__(master)
        self._font_size = 14
        self._scrolling = False
        self._speed = 4  # 滚动速度 1~10

        # ---- 标题 + 操作按钮一行 ----
        header = tk.Frame(self, bg=theme.CARD)
        header.pack(fill="x", padx=10, pady=(8, 4))
        ttk.Label(header, text="📜 提词器", style="Title.TLabel").pack(side="left")

        # 右侧按钮（先 pack 的靠右）：字号±｜清空｜滚动｜生成话题
        ttk.Button(header, text="字号 +", width=6, style="Tool.TButton",
                   command=lambda: self._resize(+2)).pack(side="right")
        ttk.Button(header, text="字号 -", width=6, style="Tool.TButton",
                   command=lambda: self._resize(-2)).pack(side="right", padx=(0, 4))
        ttk.Button(header, text="清空", width=6, style="Tool.TButton",
                   command=self._clear).pack(side="right", padx=(0, 4))
        self.scroll_btn = ttk.Button(header, text="▶ 滚动", width=7,
                                     style="Tool.TButton",
                                     command=self._toggle_scroll)
        self.scroll_btn.pack(side="right", padx=(0, 4))
        if on_generate:
            ttk.Button(header, text="生成话题", style="Accent.TButton",
                       command=on_generate).pack(side="right", padx=(0, 8))

        # ---- 滚动速度调节行 ----
        speed_row = tk.Frame(self, bg=theme.CARD)
        speed_row.pack(fill="x", padx=10)
        ttk.Label(speed_row, text="滚动速度", style="Muted.TLabel").pack(side="left")
        self.speed_scale = ttk.Scale(speed_row, from_=1, to=10,
                                     style="Speed.Horizontal.TScale",
                                     length=110, command=self._on_speed)
        self.speed_scale.set(self._speed)
        self.speed_scale.pack(side="left", padx=(8, 0), pady=2)

        # ---- 口播词编辑区 ----
        self.text = tk.Text(self, bg=theme.CARD_ALT, fg=theme.FG,
                            relief="flat", borderwidth=0, wrap="word",
                            font=(theme.FONT_FAMILY, self._font_size), height=5,
                            padx=12, pady=10, insertbackground=theme.FG,
                            highlightthickness=0)
        self.text.pack(fill="both", expand=True, padx=8, pady=(6, 8))
        self.text.insert("1.0", "在这里输入口播词……")
        self.text.tag_add("hint", "1.0", "end")
        self.text.tag_configure("hint", foreground=theme.MUTED)
        # 用户开始输入时去掉灰字提示
        self.text.bind("<Key>", self._dismiss_hint)

    # ---------- 对外 ----------

    def set_text(self, text):
        """外部填充文本（如生成的话题）。"""
        self.text.delete("1.0", "end")
        self.text.insert("1.0", text)

    # ---------- 内部 ----------

    def _toggle_scroll(self):
        """开启 / 关闭自动滚动（滚到底自动停）。"""
        if self._scrolling:
            self._stop_scroll()
        else:
            self._scrolling = True
            self.scroll_btn.configure(text="⏸ 暂停")
            self._tick()

    def _stop_scroll(self):
        self._scrolling = False
        self.scroll_btn.configure(text="▶ 滚动")

    def _tick(self):
        if not self._scrolling:
            return
        self.text.yview_scroll(1, "units")
        if self.text.yview()[1] >= 0.999:  # 到底了自动停
            self._stop_scroll()
            return
        self.after(max(30, 230 - self._speed * 20), self._tick)

    def _on_speed(self, value):
        try:
            self._speed = max(1, min(10, int(float(value))))
        except (TypeError, ValueError):
            pass

    def _dismiss_hint(self, _event=None):
        self.text.tag_remove("hint", "1.0", "end")

    def _resize(self, delta):
        """调整字号（下限 8）。"""
        self._font_size = max(8, self._font_size + delta)
        self.text.configure(font=(theme.FONT_FAMILY, self._font_size))

    def _clear(self):
        self.text.delete("1.0", "end")
