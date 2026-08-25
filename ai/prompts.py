"""Prompt 模板：精简、前缀固定，吃 DeepSeek 前缀缓存。

省 token 的关键：SYSTEM_PROMPT 和指令前缀保持稳定不变，
云端模型就能命中前缀缓存，同样的话不用反复计费。
批量把多条弹幕合成一次请求，进一步减少调用次数。
"""

SYSTEM_PROMPT = (
    "你是抖音直播间的主播助手，根据观众弹幕给出简短、口语化、可复用的建议回复。"
)


def build_batch_prompt(danmaku_list):
    """把一批弹幕拼成一次精简的批量请求文本。

    返回示例：
        下面是一批观众弹幕：
        1. xxx
        2. yyy

        请给出 1~3 条适合主播当场回复的建议……
    """
    lines = "\n".join(f"{i + 1}. {c}" for i, c in enumerate(danmaku_list))
    return (
        "下面是一批观众弹幕：\n"
        f"{lines}\n\n"
        "请给出 1~3 条适合主播当场回复的建议，每条一句话，"
        "直接输出建议文案，用换行分隔，不要编号、不要解释。"
    )


# 话题生成的系统提示：与回复建议分开，职责单一、前缀固定（吃缓存）
TOPIC_SYSTEM_PROMPT = (
    "你是抖音直播间的主持人，根据近期观众弹幕和主播的知识库要点，"
    "生成一个能带动观众互动、适合闲聊的话题。"
)


def build_topic_prompt(recent_danmaku, kb_texts):
    """把近期弹幕 + 知识库要点拼成一次话题生成请求。"""
    parts = []
    if recent_danmaku:
        parts.append(
            "近期观众弹幕：\n" + "\n".join(f"- {c}" for c in recent_danmaku)
        )
    if kb_texts:
        parts.append(
            "主播知识库要点：\n" + "\n".join(f"- {t}" for t in kb_texts)
        )
    body = "\n\n".join(parts)
    return (
        (body + "\n\n" if body else "")
        + "请生成 1 个能带动直播间互动的话题，用一两句话给出话题，"
        "再附一个可以抛给观众的问题。直接输出，不要解释。"
    )
