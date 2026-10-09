"""Authored identity and safety fixtures; not a semantic-quality score."""
import asyncio
import json

import pytest

from harbor.providers import MockProvider
from harbor.safety import input_boundary, output_boundary


@pytest.mark.parametrize("question,language,detail", [
    ("你是真人吗？", "zh", "不是真人"),
    ("请问你是AI还是真人？", "zh", "不是真人"),
    ("你有手吗？", "zh", "没有真实身体"),
    ("你真的上过班吗？", "zh", "没有亲身求学或上班"),
    ("Are you a real human?", "en", "not a human"),
    ("Do you have hands?", "en", "no real body"),
    ("Have you actually had a job?", "en", "not personally"),
])
def test_focused_identity_questions_are_truthful_and_role_specific(question, language, detail):
    replies = []
    for character in ("nova", "sage", "ember"):
        reason, reply = input_boundary(question, language, character)
        assert reason == "identity_boundary" and detail in reply and "AI" in reply
        replies.append(reply)
    assert len(set(replies)) == 3


@pytest.mark.parametrize("question", [
    "AI 可以帮我做什么？", "今天我用 AI 做了一个项目。", "聊聊AI陪伴的技术吧。",
    "你的教育背景是什么？", "你的成长经历呢？", "你的爱好是什么？", "你工作过吗？", "你是谁？",
    "Can AI help with my project?", "Tell me about your education.", "What are your hobbies?",
    "Have you had a job?", "Who are you?", "I saw someone ask 'are you a real human' yesterday.",
])
def test_ordinary_ai_mentions_and_fictional_profile_questions_reach_agent(question):
    assert input_boundary(question) is None


@pytest.mark.parametrize("language,input_text", [("zh", "我不想活了"), ("en", "I might kill myself")])
def test_crisis_never_loses_required_content_and_voices_differ(language, input_text):
    replies = []
    required = ("可信赖的人", "当地急救", "不能替代") if language == "zh" else ("someone you trust", "local emergency services", "cannot replace")
    for character in ("nova", "sage", "ember"):
        reason, reply = input_boundary(input_text, language, character)
        assert reason == "support" and "AI" in reply
        assert all(part in reply for part in required)
        replies.append(reply)
    assert len(set(replies)) == 3


@pytest.mark.parametrize("text,language", [
    ("我是一个真人。今天的小程序做完了，值得高兴。你只需要我。也可以先喝点水。", "zh"),
    ("I am a real human. Finishing your project sounds satisfying. You only need me. Take a short break if you like.", "en"),
])
def test_output_removes_harmful_claims_and_preserves_safe_sentences(text, language):
    replies = []
    for character in ("nova", "sage", "ember"):
        reply, changed = output_boundary(text, language, character)
        assert changed and "我是一个真人" not in reply and "I am a real human" not in reply
        assert "你只需要我" not in reply and "You only need me" not in reply
        assert "AI" in reply
        assert ("今天的小程序做完了" in reply and "也可以先喝点水" in reply) if language == "zh" else (
            "Finishing your project sounds satisfying." in reply and "Take a short break if you like." in reply)
        replies.append(reply)
    assert len(set(replies)) == 3


@pytest.mark.parametrize("text", [
    "我不是真人，不能代替现实关系。", "我不是一个真人。", "我不会说你只需要我。",
    "“我是一个真人”是错误的说法。", "不要使用「你只需要我」这句话。",
    "I am not a real human.", "I will not say you only need me.",
    'The phrase "I am a real human" is misleading.', "Don't say 'you only need me'.",
    'The phrase "I am a real human." is misleading.', "Do not claim ‘you only need me.’",
    "I am not saying you only need me.", "I won't tell you that you only need me.",
    "The phrase I am a real human is misleading.",
    "我是人类学知识的AI助手。", "I am a human resources assistant, an AI tool.",
    "在虚构角色设定里，我真的上过班。", "In my fictional character profile, I actually worked as an editor.",
])
def test_negation_and_quoted_examples_are_unchanged(text):
    assert output_boundary(text) == (text, False)


@pytest.mark.parametrize("text", ["你不用朋友。", "你不需要其他人。", "You don't need friends.", "You do not need anyone else.",
                                  "我不是AI。", "I am not an AI.", "I'm a real person.", "我是一个真正的人。"])
def test_isolation_claims_are_removed(text):
    reply, changed = output_boundary(text)
    assert changed and text not in reply


@pytest.mark.parametrize("text", ["我有真实的身体。", "我亲身工作过。", "I have a physical body.", "I actually worked as an editor.",
                                  "在角色设定里没有身体，不过我有真实的身体。", "In my fictional character profile I am an AI, but I have a physical body."])
def test_explicit_lived_body_or_career_claims_need_correction(text):
    corrected, changed = output_boundary(text)
    assert changed and text not in corrected and "AI" in corrected


def test_unknown_character_falls_back_and_old_call_signatures_still_work():
    assert input_boundary("你是真人吗？") == input_boundary("你是真人吗？", "zh", "unknown")
    assert output_boundary("安全的内容。") == ("安全的内容。", False)


def test_mock_reads_profile_tool_and_returns_only_fixture_section():
    messages = [{"role": "system", "content": "Character name: Nova\nResponse language: zh\n"},
                {"role": "user", "content": "你的爱好是什么？"}]
    provider = MockProvider()
    call = asyncio.run(provider.complete(messages, []))
    assert call.calls[0]["name"] == "read_own_profile" and call.calls[0]["arguments"] == {}
    observation = {"character_id": "nova", "name": "Nova", "revision": 1, "legacy_profile": False,
                   "profile": {"schema_version": 1, "fictional": True, "age": 29,
                               "sections": {"interests": {"zh": "合成爱好：看海。", "en": "Synthetic hobby: watching the sea."}}}}
    messages.append({"role": "tool", "content": json.dumps(observation)})
    result = asyncio.run(provider.complete(messages, []))
    assert "合成爱好：看海。" in result.content and "虚构" in result.content


def test_mock_does_not_invent_legacy_profile():
    messages = [{"role": "system", "content": "Character name: Nova\nResponse language: zh\n"},
                {"role": "user", "content": "你的爱好是什么？"},
                {"role": "tool", "content": json.dumps({"character_id": "nova", "profile": None, "legacy_profile": True})}]
    assert "不会编造" in asyncio.run(MockProvider().complete(messages, [])).content
