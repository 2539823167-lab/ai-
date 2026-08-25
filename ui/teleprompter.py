"""提词器面板：大字口播词 + 字号调节 + 清空 + 生成话题。"""
import tkinter as tk
from tkinter import ttk

from ui import theme


class TeleprompterPanel(ttk.Frame):
    def __init__(self, master, on_generate=None):
        super().__init__(master, style="Card.TFrame")

        # 标题 + 操作按钮一行
        header = ttk.Frame(self, style="Card.TFrame")
        header.pack(fill="x", padx=10, pady=(8, 4))
        ttk.Label(header, text="提词器", style="Title.TLabel").pack(side="left")

        # 右侧按钮（先 pack 的靠右）：生成话题｜清空｜字号-｜字号+
        ttk.Button(header, text="字号 +", width=6,
                   command=lambda: self._resize(+2)).pack(side="right")
        ttk.Button(header, text="字号 -", width=6,
                   command=lambda: self._resize(-2)).pack(side="right", padx=(0, 4))
        ttk.Button(header, text="清空", width=6,
                   command=self._clear).pack(side="right", padx=(0, 4))
        if on_generate:
            ttk.Button(header, text="生成话题", width=8,
                       command=on_generate).pack(side="right", padx=(0, 4))

        self._font_size = 14
        self.text = tk.Text(self, bg=theme.CARD_ALT, fg=theme.FG,
                            relief="flat", borderwidth=0, wrap="word",
                            font=(theme.FONT_FAMILY, self._font_size),
                            padx=12, pady=10, insertbackground=theme.FG,
                            highlightthickness=0)
        self.text.pack(fill="both", expand=True, padx=8, pady=(6, 8))
        self.text.insert("1.0", "在这里输入口播词……")
        self.text.tag_add("hint", "1.0", "end")
        self.text.tag_configure("hint", foreground=theme.MUTED)

    def set_text(self, text):
        """外部填充文本（如生成的话题）。"""
        self.text.delete("1.0", "end")
        self.text.insert("1.0", text)

    def _resize(self, delta):
        """调整字号（下限 8）。"""
        self._font_size = max(8, self._font_size + delta)
        self.text.configure(font=(theme.FONT_FAMILY, self._font_size))

    def _clear(self):
        self.text.delete("1.0", "end")
