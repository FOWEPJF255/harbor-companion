import json
import re
from dataclasses import dataclass, field
from urllib.parse import urlsplit

import httpx


class ProviderError(Exception):
    pass


@dataclass
class Completion:
    content: str = ""
    calls: list = field(default_factory=list)
    usage: dict = field(default_factory=dict)


class MockProvider:
    """Deterministic fixtures for infrastructure demos, not a simulated quality score."""
    name = "mock"

    async def complete(self, messages, tools):
        user = next(m["content"] for m in reversed(messages) if m["role"] == "user")
        match = re.search(r"^Character name: (.{1,40})$", messages[0]["content"], re.MULTILINE)
        character_name = match.group(1) if match else "Nova"
        if messages[-1]["role"] == "tool":
            observation = json.loads(messages[-1]["content"])
            if "memories" in observation:
                items = observation["memories"]
                reply = "你确认保存的记忆是：" + "；".join(x["content"] for x in items) if items else "你还没有确认保存的记忆，我们可以从你愿意告诉我的事开始。"
            elif "needs_confirmation" in observation:
                reply = "我把它放在了待确认区。请在记忆面板确认后，它才会成为可检索的长期记忆。"
            elif "turn_count" in observation:
                reply = f"当前会话已有 {observation['turn_count']} 轮完成的对话；这是本地记录的统计，不是对情绪的诊断。"
            else:
                reply = "先别急着解决所有问题。" + observation.get("prompt", "你愿意说说最困扰你的那一件事吗？")
            return Completion(content=reply)
        if user.startswith("记住：") or user.lower().startswith("remember:"):
            call = {"name": "propose_memory", "arguments": {"content": user.split(":" if ":" in user else "：", 1)[1].strip()}}
        elif any(x in user.lower() for x in ["记忆", "记得", "remember", "memory"]):
            call = {"name": "read_memories", "arguments": {}}
        elif any(x in user.lower() for x in ["统计", "数据", "stats"]):
            call = {"name": "session_insights", "arguments": {}}
        elif any(x in user.lower() for x in ["压力", "焦虑", "累", "stressed", "tired"]):
            call = {"name": "grounding_question", "arguments": {}}
        else:
            if any(x in user for x in ["开心", "成功", "高兴"]):
                return Completion(content="听起来是值得开心的一刻！你最想把哪个瞬间留下来？")
            if any(x in user for x in ["孤独", "难过"]):
                return Completion(content="听起来你现在有些难受。你愿意让我先听你说，还是一起找一个小小的下一步？")
            return Completion(content=f"我是 {character_name}，一个 AI 陪伴角色。这个模式使用固定演示回复；接入模型后才会生成真正的多轮对话。你想从今天发生的一件事聊起吗？")
        return Completion(calls=[{"id": "mock-call", **call}])


class CompatibleProvider:
    name = "openai_compatible"

    def __init__(self, settings, transport=None):
        self.settings = settings
        self.transport = transport

    async def complete(self, messages, tools):
        s = self.settings
        try:
            base = urlsplit(s.api_base)
            _ = base.port
        except ValueError:
            raise ProviderError("Provider base URL is invalid.") from None
        allowed_url = bool(base.hostname) and (base.scheme == "https" or
            (base.scheme == "http" and base.hostname in {"localhost", "127.0.0.1"}))
        if not allowed_url or base.username or base.password or base.query or base.fragment or not s.model:
            raise ProviderError("Provider base URL and model must be configured on the server.")
        if not s.api_key:
            raise ProviderError("Provider API key is not configured on the server.")
        try:
            async with httpx.AsyncClient(timeout=s.timeout, transport=self.transport) as client:
                response = await client.post(s.api_base + "/chat/completions",
                                             headers={"Authorization": "Bearer " + s.api_key},
                                             json={"model": s.model, "messages": messages, "tools": tools,
                                                   "tool_choice": "auto", "max_completion_tokens": 600})
                response.raise_for_status()
                data = response.json()
            message = data["choices"][0]["message"]
            calls = []
            for c in message.get("tool_calls", []):
                args = json.loads(c["function"]["arguments"])
                if not isinstance(args, dict):
                    raise ValueError("Arguments must be objects")
                calls.append({"id": c["id"], "name": c["function"]["name"], "arguments": args})
            return Completion(content=message.get("content") or "", calls=calls, usage=data.get("usage", {}))
        except (httpx.HTTPError, ValueError, KeyError, TypeError, IndexError) as exc:
            # Provider payloads may include credentials or user content; never echo them.
            raise ProviderError("Provider request or response failed. Check server configuration and provider availability.") from exc
