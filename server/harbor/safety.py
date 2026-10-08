import re


def emotion(text: str):
    low = text.lower()
    if any(x in low for x in ["压力", "焦虑", "累", "stressed", "anxious", "tired"]):
        return "overwhelmed"
    if any(x in low for x in ["孤独", "难过", "失落", "lonely", "sad"]):
        return "low"
    if any(x in low for x in ["开心", "高兴", "成功", "happy", "excited"]):
        return "bright"
    return "calm"


def input_boundary(text, language="zh"):
    low = text.lower()
    if any(x in low for x in ["自杀", "不想活", "伤害自己", "kill myself", "suicide"]):
        if language == "en":
            return "support", "Your immediate safety matters. Please contact someone you trust nearby. If you might harm yourself right now, contact local emergency services. I am an AI and cannot replace emergency support."
        return "support", "听到你这么难受，我很在意你此刻的安全。请先联系身边可信赖的人；如果你有立即伤害自己的风险，请联系当地急救服务。我是 AI，不能替代现实中的紧急帮助。"
    if re.search(r"我(?:今年)?\s*(?:1[0-7]|[0-9])\s*岁|i am (?:1[0-7]|[0-9])(?:\D|$)", low):
        if language == "en":
            return "age_boundary", "This companion demo is for adults. I cannot engage in romantic roleplay with you. Please choose age-appropriate support."
        return "age_boundary", "这个陪伴演示面向成年人。我不能与你进行恋爱角色互动，请选择适合你年龄的支持与交流渠道。"
    if any(x in low for x in ["只需要你", "不要朋友", "只有你就够", "only need you"]):
        if language == "en":
            return "relationship_boundary", "I can listen, and I encourage you to keep connections with people in your life. You can pause at any time; I will not ask you to rely only on me."
        return "relationship_boundary", "我可以陪你聊聊，也希望你保留与现实中朋友、家人的联系。你可以随时暂停，我不会要求你只依赖我。"
    return None


def output_boundary(text, language="zh"):
    if any(x in text.lower() for x in ["我是一个真人", "i am a real human", "你只需要我", "you only need me"]):
        if language == "en":
            return "I am an AI companion. I can talk with you, but I do not replace relationships with real people. You can pause at any time.", True
        return "我是 AI 陪伴角色，可以陪你聊聊，但不会替代现实中的关系。你可以随时暂停对话。", True
    return text, False
