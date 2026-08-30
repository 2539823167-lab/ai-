"""UI 主题：集中管理配色、字体与 ttk 样式（深色现代主题）。

所有面板都从这里取颜色与字体，改主题只改这一处，便于统一换肤。
"""
import tkinter as tk
from tkinter import ttk

# ---- 配色（深色主题）----
BG = "#15151F"          # 窗口背景
CARD = "#1E1E2E"        # 卡片/面板背景
CARD_ALT = "#262637"    # 次级背景（输入框、列表、建议文案底）
CARD_DEEP = "#1A1A28"   # 三级背景（日志、状态栏）
BORDER = "#33334A"      # 边框
FG = "#E8E8F2"          # 主文字
MUTED = "#8A8AA0"       # 次要文字
ACCENT = "#4FC3F7"      # 强调色（青蓝）
ACCENT_HOVER = "#79D4FF"
ACCENT_DARK = "#1B2A3A" # 强调色深底（按下态）

SUCCESS = "#66BB6A"
WARNING = "#FFB74D"
DANGER = "#EF5350"

# 回复来源 → 颜色（模板=绿 / 本地=蓝 / 云端=紫 / 兜底=灰）
SOURCE_COLORS = {
    "template": "#4CAF50",
    "local":    "#4FC3F7",
    "cloud":    "#AB47BC",
    "fallback": "#8A8AA0",
}

# 弹幕用户昵称的随机颜色池
USER_COLORS = [
    "#FF8A80", "#FFD54F", "#81C784", "#4FC3F7",
    "#B39DDB", "#F48FB1", "#4DB6AC", "#FFB74D",
]

# ---- 字体 ----
FONT_FAMILY = "Microsoft YaHei"
FONT_TITLE = (FONT_FAMILY, 12, "bold")
FONT_BODY = (FONT_FAMILY, 10)
FONT_SMALL = (FONT_FAMILY, 9)
FONT_NUM = (FONT_FAMILY, 16, "bold")


class Card(tk.Frame):
    """带 1px 边框的卡片容器：各面板的统一基座。"""

    def __init__(self, master, **kw):
        super().__init__(master, bg=CARD, highlightbackground=BORDER,
                         highlightthickness=1, **kw)


class PlaceholderEntry(ttk.Entry):
    """带占位提示的输入框：为空时显示灰字提示，聚焦即清掉。

    get() 在占位显示期间返回空串，调用方无需额外判断。
    """

    def __init__(self, master, placeholder="", **kw):
        super().__init__(master, **kw)
        self._placeholder = placeholder
        self._showing = False
        self.bind("<FocusIn>", self._on_focus_in)
        self.bind("<FocusOut>", self._on_focus_out)
        self._show()

    def _show(self):
        if not super().get():
            self._showing = True
            self.configure(foreground=MUTED)
            super().delete(0, "end")
            super().insert(0, self._placeholder)

    def _on_focus_in(self, _event=None):
        if self._showing:
            self._showing = False
            super().delete(0, "end")
            self.configure(foreground=FG)

    def _on_focus_out(self, _event=None):
        self._show()

    def get(self):
        """占位显示时视为空。"""
        return "" if self._showing else super().get()

    def insert(self, index, text):
        """占位显示期间插入内容时，先清掉占位文字（程序赋值同样安全）。"""
        if self._showing:
            self._showing = False
            super().delete(0, "end")
            self.configure(foreground=FG)
        super().insert(index, text)

    def clear(self):
        """清空内容；失焦后占位提示会自动恢复。"""
        self._showing = False
        super().delete(0, "end")
        self.configure(foreground=FG)


def apply_style(root):
    """配置全局 ttk 样式（需在创建任何 ttk 组件前调用）。返回 style 对象。"""
    style = ttk.Style(root)
    try:
        style.theme_use("clam")  # clam 对颜色定制最友好
    except Exception:
        pass

    root.configure(bg=BG)

    # 框架
    style.configure("App.TFrame", background=BG)
    style.configure("Card.TFrame", background=CARD)

    # 标签
    style.configure("Card.TLabel", background=CARD, foreground=FG, font=FONT_BODY)
    style.configure("Title.TLabel", background=CARD, foreground=FG, font=FONT_TITLE)
    style.configure("Muted.TLabel", background=CARD, foreground=MUTED, font=FONT_SMALL)

    # 普通按钮
    style.configure("TButton", background=CARD_ALT, foreground=FG,
                    borderwidth=0, focusthickness=0, focuscolor=CARD_ALT,
                    padding=(10, 6), font=FONT_BODY)
    style.map("TButton",
              background=[("active", BORDER), ("pressed", ACCENT_DARK)],
              foreground=[("disabled", MUTED)])

    # 强调按钮（面板主操作，实心青蓝）
    style.configure("Accent.TButton", background=ACCENT, foreground="#0D1B26",
                    borderwidth=0, focusthickness=0, focuscolor=ACCENT,
                    padding=(12, 6), font=(FONT_FAMILY, 10, "bold"))
    style.map("Accent.TButton",
              background=[("active", ACCENT_HOVER), ("pressed", ACCENT_DARK)],
              foreground=[("disabled", MUTED)])

    # 小工具按钮（面板头部，紧凑）
    style.configure("Tool.TButton", background=CARD_ALT, foreground=FG,
                    borderwidth=0, focusthickness=0, focuscolor=CARD_ALT,
                    padding=(8, 3), font=FONT_SMALL)
    style.map("Tool.TButton",
              background=[("active", BORDER), ("pressed", ACCENT_DARK)],
              foreground=[("disabled", MUTED)])

    # 危险按钮（删除等，红字提示）
    style.configure("Danger.TButton", background=CARD_ALT, foreground=DANGER,
                    borderwidth=0, focusthickness=0, focuscolor=CARD_ALT,
                    padding=(8, 3), font=FONT_SMALL)
    style.map("Danger.TButton",
              background=[("active", "#4A2A33"), ("pressed", ACCENT_DARK)],
              foreground=[("disabled", MUTED)])

    # 输入框
    style.configure("TEntry", fieldbackground=CARD_ALT, foreground=FG,
                    insertcolor=FG, bordercolor=BORDER,
                    lightcolor=BORDER, darkcolor=BORDER)

    # 微调框（聚合窗口等数字输入）
    style.configure("TSpinbox", fieldbackground=CARD_ALT, foreground=FG,
                    insertcolor=FG, bordercolor=BORDER, lightcolor=BORDER,
                    darkcolor=BORDER, arrowcolor=MUTED,
                    background=CARD_ALT, buttonbackground=CARD_ALT)
    style.map("TSpinbox",
              fieldbackground=[("readonly", CARD_ALT)],
              foreground=[("disabled", MUTED)])

    # 滑块（提词器滚动速度等）
    style.configure("Speed.Horizontal.TScale", troughcolor=CARD_ALT,
                    background=ACCENT, bordercolor=CARD,
                    lightcolor=BORDER, darkcolor=BORDER)

    # 滚动条（深色化，clam 下部分属性可能不生效，尽力而为）
    style.configure("Vertical.TScrollbar", background=CARD_ALT,
                    troughcolor=CARD, bordercolor=CARD, arrowcolor=MUTED)

    return style
