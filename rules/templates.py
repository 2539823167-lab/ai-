"""L1 模板：关键词 → 固定回复，0 token / 0 元。

高频问题（问价格、求关注、欢迎新人等）不需要 AI，直接命中模板秒回，
这是省 token 的第一道防线。模板可自由增删。
"""

TEMPLATES = [
    {"keywords": ["多少钱", "价格", "价位", "怎么卖", "贵不贵"], "reply": "亲，这款直播间有专属优惠，具体价格看小黄车，下单还有赠品哦～"},
    {"keywords": ["关注", "加关注", "点关注", "关注了"], "reply": "谢谢关注！新粉记得点个关注不迷路，每天都有直播～"},
    {"keywords": ["新人", "第一次来", "刚来", "新来的"], "reply": "欢迎新朋友！有什么想看的、想问的，打在公屏上～"},
    {"keywords": ["礼物", "谢谢主播", "打赏"], "reply": "感谢老板的礼物，比心！"},
    {"keywords": ["你好", "哈喽", "hello", "在吗"], "reply": "你好呀，欢迎来到直播间～"},
    {"keywords": ["优惠券", "优惠", "券", "活动"], "reply": "直播间现在有活动，记得领券再下单更划算～"},
]


def match_template(content):
    """命中任一模板关键词则返回回复文本，未命中返回 None。"""
    for t in TEMPLATES:
        for kw in t["keywords"]:
            if kw in content:
                return t["reply"]
    return None
