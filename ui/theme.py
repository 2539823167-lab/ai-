"""UI 主题：集中管理配色、字体与 ttk 样式（深色现代主题）。

所有面板都从这里取颜色与字体，改主题只改这一处，便于统一换肤。
"""
from tkinter import ttk

# ---- 配色（深色主题）----
BG = "#1E1E2E"          # 窗口背景
CARD = "#2A2A3C"        # 卡片/面板背景
CARD_ALT = "#232334"    # 次级背景（输入框、列表、建议文案底）
BORDER = "#3A3A4E"      # 边框
FG = "#E6E6F0"          # 主文字
MUTED = "#8A8AA0"       # 次要文字
ACCENT = "#4FC3F7"      # 强调色（青蓝）
ACCENT_DARK = "#1B2A3A" # 强调色深底（按下态）

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

    # 按钮
    style.configure("TButton", background=CARD_ALT, foreground=FG,
                    borderwidth=0, focusthickness=0, padding=(10, 6),
                    font=FONT_BODY)
    style.map("TButton",
              background=[("active", ACCENT), ("pressed", ACCENT_DARK)],
              foreground=[("active", "#FFFFFF")])

    # 输入框
    style.configure("TEntry", fieldbackground=CARD_ALT, foreground=FG,
                    insertcolor=FG, bordercolor=BORDER,
                    lightcolor=BORDER, darkcolor=BORDER)

    # 滚动条（深色化，clam 下部分属性可能不生效，尽力而为）
    style.configure("Vertical.TScrollbar", background=CARD_ALT,
                    troughcolor=CARD, bordercolor=CARD, arrowcolor=MUTED)

    return style
