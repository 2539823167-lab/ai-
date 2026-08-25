"""敏感词过滤。

对进入 AI 判断 / 模板匹配的弹幕文本做简单清洗，
避免脏词影响 AI 输出。示例词表可自行扩充。
"""

SENSITIVE_WORDS = ["傻逼", "滚蛋", "垃圾"]


def filter_text(text):
    """把敏感词替换为等长 * 号，返回过滤后的文本。"""
    result = text
    for w in SENSITIVE_WORDS:
        if w in result:
            result = result.replace(w, "*" * len(w))
    return result
