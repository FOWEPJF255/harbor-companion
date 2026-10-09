import json
import re
from dataclasses import dataclass, field
from urllib.parse import urlsplit

import httpx


class ProviderError(Exception):
    def __init__(self, message, metadata=None):
        super().__init__(message)
        self.metadata = metadata or {}


@dataclass
class Completion:
    content: str = ""
    calls: list = field(default_factory=list)
    usage: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)


def safe_usage(value):
    """Retain numeric usage only, never provider-supplied text or hidden reasoning."""
    if not isinstance(value, dict):
        raise ValueError("Usage must be an object")
    result = {}
    for key in ("prompt_tokens", "completion_tokens", "total_tokens", "prompt_cache_hit_tokens", "prompt_cache_miss_tokens"):
        count = value.get(key)
        if isinstance(count, int) and not isinstance(count, bool) and count >= 0:
            result[key] = count
    for key, child in (("prompt_tokens_details", "cached_tokens"), ("completion_tokens_details", "reasoning_tokens")):
        details = value.get(key)
        count = details.get(child) if isinstance(details, dict) else None
        if isinstance(count, int) and not isinstance(count, bool) and count >= 0:
            result[key] = {child: count}
    return result


class MockProvider:
    """Deterministic fixtures for infrastructure demos, not a simulated quality score."""
    name = "mock"

    async def complete(self, messages, tools):
        user = next(m["content"] for m in reversed(messages) if m["role"] == "user")
        match = re.search(r"^Character name: (.{1,40})$", messages[0]["content"], re.MULTILINE)
        character_name = match.group(1) if match else "Nova"
        english = "\nResponse language: en\n" in messages[0]["content"]
        if messages[-1]["role"] == "tool":
            observation = json.loads(messages[-1]["content"])
            if "error" in observation:
                reply = ("The tool could not complete this action: " if english else "工具未完成这次动作：") + observation["error"]
            elif "answer" in observation:
                reply = observation["answer"]
            elif "memories" in observation:
                items = observation["memories"]
                reply = (("Your approved memories: " if english else "你确认保存的记忆是：") + "; ".join(x["content"] for x in items)) if items else ("You have no approved memories yet." if english else "你还没有确认保存的记忆，我们可以从你愿意告诉我的事开始。")
            elif "needs_confirmation" in observation:
                reply = "This proposal is transient. Confirm it in Memory before it becomes retrievable long-term memory." if english else "这条建议暂存在待确认区。请在记忆面板确认后，它才会成为可检索的长期记忆。"
            elif "turn_count" in observation:
                reply = f"This session has {observation['turn_count']} completed turns. These are local counts, not an emotional diagnosis." if english else f"当前会话已有 {observation['turn_count']} 轮完成的对话；这是本地记录的统计，不是对情绪的诊断。"
            else:
                reply = "There is no need to solve everything at once. Would you like to tell me what feels hardest right now?" if english else "先别急着解决所有问题。" + observation.get("prompt", "你愿意说说最困扰你的那一件事吗？")
            return Completion(content=reply)
        if user.startswith("记住：") or user.lower().startswith("remember:"):
            call = {"name": "propose_memory", "arguments": {"content": user.split(":" if ":" in user else "：", 1)[1].strip()}}
        elif any(x in user.lower() for x in ["合成", "synthetic", "demo data"]):
            call = {"name": "analyze_demo_data", "arguments": {"question": user}}
        elif any(x in user.lower() for x in ["记忆", "记得", "remember", "memory"]):
            call = {"name": "read_memories", "arguments": {}}
        elif any(x in user.lower() for x in ["统计", "数据", "stats"]):
            call = {"name": "session_insights", "arguments": {}}
        elif any(x in user.lower() for x in ["压力", "焦虑", "累", "stressed", "tired"]):
            call = {"name": "grounding_question", "arguments": {}}
        else:
            if any(x in user.lower() for x in ["开心", "成功", "高兴", "happy", "excited"]):
                return Completion(content="That sounds like a happy moment. Which part would you like to share?" if english else "听起来是值得开心的一刻！你最想把哪个瞬间留下来？")
            if any(x in user.lower() for x in ["孤独", "难过", "lonely", "sad"]):
                return Completion(content="That sounds difficult. Would you prefer that I listen, or help you think of a small next step?" if english else "听起来你现在有些难受。你愿意让我先听你说，还是一起找一个小小的下一步？")
            if english:
                return Completion(content=f"I am {character_name}, an AI companion. This is a fixed mock reply; genuine multi-turn responses require a model API. What happened in your day?")
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
        official_deepseek = base.hostname == "api.deepseek.com"
        payload = {"model": s.model, "messages": messages, "tools": tools, "tool_choice": "auto"}
        if official_deepseek:
            payload.update(max_tokens=600, thinking={"type": "disabled"})
        else:
            payload["max_completion_tokens"] = 600
        metadata = {"protocol": "deepseek_official" if official_deepseek else "openai_compatible"}
        try:
            async with httpx.AsyncClient(timeout=s.timeout, transport=self.transport) as client:
                response = await client.post(s.api_base.rstrip("/") + "/chat/completions",
                                             headers={"Authorization": "Bearer " + s.api_key},
                                             json=payload)
                metadata["http_status"] = response.status_code
                response.raise_for_status()
                data = response.json()
            choice = data["choices"][0]
            if not isinstance(choice, dict):
                raise ValueError("Completion choice must be an object")
            usage = safe_usage(data.get("usage", {}))
            metadata["usage"] = usage
            finish = choice.get("finish_reason")
            recognized = {"stop", "tool_calls", "length", "content_filter", "insufficient_system_resource", "aborted"}
            metadata["finish_reason"] = finish if isinstance(finish, str) and finish in recognized else "unknown"
            if finish in {"length", "content_filter", "insufficient_system_resource", "aborted"}:
                metadata["failure_class"] = "truncated" if finish == "length" else "generation_failed"
                raise ProviderError("Provider generation did not complete successfully.", metadata)
            if (official_deepseek and finish not in {"stop", "tool_calls"}) or (finish is not None and finish not in recognized):
                raise ValueError("Invalid completion finish reason")
            message = choice["message"]
            if not isinstance(message, dict):
                raise ValueError("Completion message must be an object")
            if message.get("refusal"):
                metadata["failure_class"] = "refusal"
                raise ProviderError("Provider declined the request.", metadata)
            if not isinstance(message.get("content") or "", str):
                raise ValueError("Invalid completion fields")
            calls = []
            tool_calls = message.get("tool_calls", [])
            if not isinstance(tool_calls, list) or len(tool_calls) > 4:
                raise ValueError("Invalid tool calls")
            for c in tool_calls:
                if not isinstance(c["id"], str) or not re.fullmatch(r"[a-zA-Z0-9_-]{1,128}", c["id"]):
                    raise ValueError("Invalid tool call ID")
                if not isinstance(c["function"]["name"], str) or not re.fullmatch(r"[a-zA-Z0-9_]{1,64}", c["function"]["name"]):
                    raise ValueError("Invalid tool name")
                if not isinstance(c["function"]["arguments"], str) or len(c["function"]["arguments"]) > 4096:
                    raise ValueError("Oversized tool arguments")
                args = json.loads(c["function"]["arguments"])
                if not isinstance(args, dict):
                    raise ValueError("Arguments must be objects")
                calls.append({"id": c["id"], "name": c["function"]["name"], "arguments": args})
            if finish == "tool_calls" and not calls or finish == "stop" and calls:
                raise ValueError("Finish reason contradicts the tool calls")
            # reasoning_content and raw provider payloads are deliberately discarded.
            return Completion(content=message.get("content") or "", calls=calls, usage=usage, metadata=metadata)
        except (httpx.HTTPError, ValueError, KeyError, TypeError, IndexError) as exc:
            # Provider payloads may include credentials or user content; never echo them.
            metadata["failure_class"] = "transport" if isinstance(exc, httpx.HTTPError) else "invalid_response"
            raise ProviderError("Provider request or response failed. Check server configuration and provider availability.", metadata) from None
