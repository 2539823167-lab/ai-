"""回复建议面板：来源彩色标签 + 建议文案 + 一键复制。"""
import tkinter as tk
from tkinter import ttk

from ui import theme

# 来源 → 中文名
SOURCE_NAMES = {
    "template": "模板",
    "local": "本地AI",
    "cloud": "云端AI",
    "fallback": "兜底",
}


class ReplyPanel(ttk.Frame):
    def __init__(self, master):
        super().__init__(master, style="Card.TFrame")
        ttk.Label(self, text="回复建议", style="Title.TLabel").pack(
            anchor="w", padx=10, pady=(8, 4))

        self.source_label = ttk.Label(self, text="来源：-", style="Muted.TLabel")
        self.source_label.pack(anchor="w", padx=10)

        self.text = tk.Text(self, bg=theme.CARD_ALT, fg=theme.FG,
                            relief="flat", borderwidth=0, wrap="word",
                            font=(theme.FONT_FAMILY, 12), height=8,
                            padx=12, pady=10, highlightthickness=0)
        self.text.pack(fill="both", expand=True, padx=8, pady=(6, 0))

        self.copy_btn = ttk.Button(self, text="复制建议", command=self._copy)
        self.copy_btn.pack(anchor="e", padx=10, pady=8)

    def show(self, suggestion):
        """展示一条回复建议（已在主线程），来源标签按类型着色。"""
        name = SOURCE_NAMES.get(suggestion.source, suggestion.source)
        color = theme.SOURCE_COLORS.get(suggestion.source, theme.MUTED)
        self.source_label.configure(
            text=f"来源：{name}（约 {suggestion.cost:.3f} 元）",
            foreground=color,
        )
        self.text.delete("1.0", "end")
        self.text.insert("1.0", suggestion.content)

    def _copy(self):
        """把建议文案复制到剪贴板。"""
        content = self.text.get("1.0", "end").strip()
        if content:
            self.clipboard_clear()
            self.clipboard_append(content)
