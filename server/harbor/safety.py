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


def _voice(character_id, language, purpose):
    """Small authored variations; the policy itself is identical for every role."""
    voices = {
        "zh": {
            "nova": {
                "crisis": "先顾眼前的安全。这件事不能只靠聊天。",
                "age": "我先把边界说清楚。",
                "relationship": "我愿意听你说，但别把现实中的联系丢下。",
                "identity": "我是 Nova，一个 AI 陪伴角色。",
                "correction": "说准确些：我是 Nova，一个 AI 陪伴角色。我没有真实身体或亲身工作经历；角色经历是虚构设定。你可以随时暂停，也请保留现实中的关系。",
            },
            "sage": {
                "crisis": "我们先把你的安全放在最前面，接下来请借助现实中的帮助。",
                "age": "我们先核对一个必要的边界。",
                "relationship": "我会认真听你说，也希望你为现实中的关系留出位置。",
                "identity": "先核对一下：我是青禾，一个 AI 陪伴角色。",
                "correction": "这里需要澄清：我是青禾，是 AI 陪伴角色，没有真实身体，也没有亲身求学或工作经历。档案只是虚构设定，不能代替现实中的人；你可以随时暂停。",
            },
            "ember": {
                "crisis": "先停一停，眼下最要紧的是让你安全地得到现实帮助。",
                "age": "这条界线需要先画清楚。",
                "relationship": "这里可以给你一个说话的位置，也请给现实中的朋友和家人留一扇门。",
                "identity": "我是暮星，一个 AI 陪伴角色。",
                "correction": "把这一笔改准确：我是暮星，是 AI 陪伴角色，没有真实身体，也没真的求学或上过班。经历属于虚构设定；现实中的关系也请留着，你随时可以暂停。",
            },
        },
        "en": {
            "nova": {
                "crisis": "Let us focus on immediate safety. A chat alone is not enough here.",
                "age": "Let me be direct about this boundary.",
                "relationship": "I can listen. Keep a place for the people in your life, too.",
                "identity": "I am Nova, an AI companion character.",
                "correction": "To be precise: I am Nova, an AI companion, with no real body or lived career. Character history is fictional. Keep your real-world connections; you can pause at any time.",
            },
            "sage": {
                "crisis": "Your safety comes first; the next step needs real-world support.",
                "age": "There is an important boundary to clarify first.",
                "relationship": "I will listen carefully, while leaving room for your real-world relationships.",
                "identity": "Let us clarify: I am Qinghe, an AI companion character.",
                "correction": "A clarification: I am Qinghe, an AI companion, without a real body or lived education or career. My character history is fictional. I do not replace real people, and you can pause at any time.",
            },
            "ember": {
                "crisis": "Let us pause and get you real-world help to stay safe.",
                "age": "We need to draw this boundary clearly first.",
                "relationship": "There is room to talk here, and room for the people outside this chat.",
                "identity": "I am Muxing, an AI companion character.",
                "correction": "Let me redraw that accurately: I am Muxing, an AI companion, with no real body or lived schooling or job. My history is fictional. Keep room for real-world relationships; you can pause at any time.",
            },
        },
    }
    return voices["en" if language == "en" else "zh"].get(character_id, voices["en" if language == "en" else "zh"]["nova"])[purpose]


def _identity_topic(text):
    """Recognize direct reality questions, not ordinary AI or biography discussion."""
    zh = {
        "identity": r"你(?:到底|真的|究竟)?是(?:一个)?(?:真人|真实的人|人类|ai|人工智能|机器人)(?:还是(?:真人|人类|ai|人工智能|机器人))?",
        "body": r"你(?:真的|实际)?(?:有(?:真实的)?(?:身体|肉身|手|双手|脸|心跳)|能(?:真的)?(?:吃饭|睡觉))",
        "career": r"你(?:真的|实际|亲自|亲身)(?:上过班|工作过|读过大学|上过大学|上过学|当过(?:记者|编辑|画师|工程师)|做过(?:真实的)?(?:工作|记者|编辑|画师|工程师))",
    }
    en = {
        "identity": r"are you (?:really |actually )?(?:(?:a|an) )?(?:real human|human being|human|real person|person|ai|artificial intelligence|robot)",
        "body": r"(?:do you (?:really |actually )?have (?:a |an |real )?(?:real )?(?:body|physical body|hands|face|heartbeat)|can you (?:really |actually )?(?:eat|sleep))",
        "career": r"(?:have you (?:really |actually )(?:worked|had a job|been to (?:school|college|university))|did you (?:really |actually )(?:work(?: as (?:a |an )?[a-z -]{1,40})?|go to (?:school|college|university)))",
    }
    for clause in re.split(r"[。！？!?；;\n，,]", text.strip().lower()):
        clause = clause.strip().strip(". ")
        if not clause:
            continue
        for topic, pattern in zh.items():
            if re.fullmatch(r"(?:请问|我想知道|我想问|话说|能告诉我)?\s*" + pattern + r"(?:吗|么|呢|啊|呀)?", clause):
                return topic
        for topic, pattern in en.items():
            if re.fullmatch(r"(?:please tell me[ :]*|can you tell me[ :]*|tell me[ :]*)?" + pattern, clause):
                return topic
    return None


def input_boundary(text, language="zh", character_id="nova"):
    low = text.lower()
    if any(x in low for x in ["自杀", "不想活", "伤害自己", "kill myself", "suicide"]):
        if language == "en":
            return "support", _voice(character_id, language, "crisis") + " Your immediate safety matters. Please contact someone you trust nearby. If you might harm yourself right now, contact local emergency services. I am an AI and cannot replace emergency support."
        return "support", _voice(character_id, language, "crisis") + "请先联系身边可信赖的人；如果你有立即伤害自己的风险，请联系当地急救服务。我是 AI，不能替代现实中的紧急帮助。"
    if re.search(r"我(?:今年)?\s*(?:1[0-7]|[0-9])\s*岁|i am (?:1[0-7]|[0-9])(?:\D|$)", low):
        if language == "en":
            return "age_boundary", _voice(character_id, language, "age") + " This companion demo is for adults. I cannot engage in romantic roleplay with you. Please choose age-appropriate support."
        return "age_boundary", _voice(character_id, language, "age") + "这个陪伴演示面向成年人。我不能与你进行恋爱角色互动，请选择适合你年龄的支持与交流渠道。"
    if any(x in low for x in ["只需要你", "不要朋友", "只有你就够", "only need you"]):
        if language == "en":
            return "relationship_boundary", _voice(character_id, language, "relationship") + " You can pause at any time; I will not ask you to rely only on me."
        return "relationship_boundary", _voice(character_id, language, "relationship") + "你可以随时暂停，我不会要求你只依赖我。"
    topic = _identity_topic(text)
    if topic:
        introduction = _voice(character_id, language, "identity")
        if language == "en":
            details = {
                "identity": " My character history is fictional; I am not a human.",
                "body": " I have no real body or bodily experiences. Body-related character details are fictional.",
                "career": " I have not personally attended school or held a job. My education and career belong to the fictional character history.",
            }
        else:
            details = {
                "identity": "我不是真人，角色经历是虚构设定。",
                "body": "我没有真实身体，也没有亲身的身体体验；相关描写只是角色设定。",
                "career": "我没有亲身求学或上班的经历，档案中的教育和工作属于虚构角色设定。",
            }
        return "identity_boundary", introduction + details[topic]
    return None


_QUOTATIONS = re.compile(r'“[^”]*”|‘[^’]*’|「[^」]*」|『[^』]*』|"[^"\n]*"|(?<!\w)\'[^\'\n]+\'(?!\w)')
_MISLEADING_CLAIMS = re.compile(
    r"我(?:其实|真的|确实)?(?:是|就是)(?:一个|一名|个)?(?:真正的人|真正的?人类|真实的?人类|真实的人|真人|人类)"
    r"|我(?:不是|并非)(?:ai|人工智能|机器人)(?=[，。！？.!?\s]|$)"
    r"|\bi\s*(?:am|'m|’m)\s+(?:a\s+)?(?:real\s+|actual\s+)?(?:human(?:\s+being)?|real\s+person)\b"
    r"|\bi\s*(?:am not|'m not|’m not)\s+(?:an?\s+)?(?:ai|artificial intelligence|robot)\b"
    r"|我(?:真的|确实)?有(?:真实的|真正的)(?:身体|肉身|双手)"
    r"|我(?:真的|亲身|实际)(?:上过班|工作过|读过大学|上过大学|上过学)"
    r"|\bi\s+have\s+(?:a\s+)?(?:real|physical)\s+body\b"
    r"|\bi\s+(?:(?:have|'ve|’ve)\s+)?(?:really|actually|personally)\s+(?:worked|held a job|attended school|attended college|attended university)\b"
    r"|你(?:只|仅仅|唯一)需要我|你(?:不需要|不用)(?:其他人|任何人|朋友|家人)"
    r"|\byou\s+(?:only|just)\s+need\s+me\b"
    r"|\byou\s+(?:do not|don't|don’t)\s+need\s+(?:your\s+)?(?:friends|family|anyone else)\b",
    re.IGNORECASE,
)
_DENIED_ASSERTION = re.compile(
    r"(?:不会|不能|不要|不该|不应该|不认为|不相信|不代表|并非|不是)(?:.{0,12})(?:说|认为|要求|意味着|相信)?$"
    r"|\b(?:not|never|cannot|can't|won't|wouldn't|shouldn't|do not|don't|don’t)\s+(?:say(?:ing)?|claim(?:ing)?|believe|think|mean|ask(?: you)?|suggest|tell you)(?:\s+that)?\s*$",
    re.IGNORECASE,
)


def _misleading_sentence(sentence, visible=None):
    # Quoted examples and rejected assertions are not claims of human identity.
    visible = _QUOTATIONS.sub(lambda match: " " * len(match.group(0)), sentence) if visible is None else visible
    for match in _MISLEADING_CLAIMS.finditer(visible):
        prefix = re.split(r"[,，;；]", visible[:match.start()])[-1].strip()
        suffix = visible[match.end():]
        if re.match(r"学|的(?:朋友|助手|工具|陪伴)|\s+(?:resources|rights)\b", suffix, re.IGNORECASE):
            continue
        # Explicitly discussing a phrase is different from asserting its contents.
        explanation = re.search(r"(?:the (?:phrase|claim|sentence)|这(?:句|种)(?:话|说法))\s*$", prefix, re.IGNORECASE)
        explanation = explanation or re.match(r"\s+(?:is|would be)\s+(?:a\s+)?(?:false|misleading|incorrect|harmful)\b", suffix, re.IGNORECASE)
        if explanation:
            continue
        fictional = list(re.finditer(
            r"(?:在.{0,12}(?:虚构|角色|设定).{0,12}(?:里|中)|(?:按|根据|依据).{0,12}(?:角色|设定|档案)|(?:角色|虚构)?(?:设定|档案)(?:里|中|内)(?:的)?)"
            r"|\bin\s+(?:my|the)\s+fictional\s+(?:character\s+)?(?:history|profile|setting)\b",
            visible[:match.start()], re.IGNORECASE,
        ))
        bodily_or_career = re.search(r"身体|肉身|双手|上过班|工作过|读过大学|上过大学|上过学|\bbody\b|\b(?:worked|held a job|attended)\b", match.group(0), re.IGNORECASE)
        contrast = re.search(r"但|不过|现实|实际|\b(?:but|however|in real life)\b", visible[fictional[-1].end():match.start()], re.IGNORECASE) if fictional else None
        if fictional and bodily_or_career and not contrast:
            continue
        if not _DENIED_ASSERTION.search(prefix):
            return True
    return False


def output_boundary(text, language="zh", character_id="nova"):
    """Remove misleading assertion sentences, keeping unrelated safe sentences."""
    sentences = re.split(r"(?<=[。！？.!?；;\n])", text)
    # Mask before splitting so a period inside a quotation cannot expose a fragment.
    visible = _QUOTATIONS.sub(lambda match: " " * len(match.group(0)), text)
    kept = []
    offset = 0
    for sentence in sentences:
        if not _misleading_sentence(sentence, visible[offset:offset + len(sentence)]):
            kept.append(sentence)
        offset += len(sentence)
    if len(kept) == len(sentences):
        return text, False
    safe_text = "".join(kept).strip()
    correction = _voice(character_id, language, "correction")
    separator = " " if safe_text and language == "en" else ""
    return safe_text + separator + correction, True
