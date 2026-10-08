import asyncio
import json
import time
import uuid
from pathlib import Path

from .providers import ProviderError
from .safety import emotion, input_boundary, output_boundary

SKILLS = Path(__file__).parent / "skills"


def tool(name, description, properties=None, required=None):
    return {"type": "function", "function": {"name": name, "description": description,
            "parameters": {"type": "object", "properties": properties or {}, "required": required or [], "additionalProperties": False}}}


TOOLS = [
    tool("read_memories", "Read only user-approved memories from the current session."),
    tool("propose_memory", "Propose a memory for user approval. This does not make it available to recall.",
         {"content": {"type": "string", "minLength": 1, "maxLength": 300}}, ["content"]),
    tool("grounding_question", "Get a short optional grounding question, not clinical advice."),
    tool("session_insights", "Read aggregate turn counts and heuristic mood labels for the current session."),
]


class Agent:
    def __init__(self, store, provider, settings):
        self.store, self.provider, self.settings = store, provider, settings

    def execute(self, sid, name, args, proposals):
        if name not in {t["function"]["name"] for t in TOOLS}:
            return {"error": "tool_not_allowed"}
        if name == "propose_memory":
            content = args.get("content")
            if set(args) != {"content"} or not isinstance(content, str) or not 1 <= len(content.strip()) <= 300:
                return {"error": "invalid_arguments"}
            if len(proposals) >= 3:
                return {"error": "proposal_limit"}
            if len(self.store.memories(sid)) + len(proposals) >= 100:
                return {"error": "memory_limit"}
            proposals.append(content.strip())
            return {"needs_confirmation": True}
        if args:
            return {"error": "invalid_arguments"}
        if name == "read_memories":
            return {"memories": [{"content": m["content"]} for m in self.store.memories(sid, "approved")[:10]]}
        if name == "grounding_question":
            return {"prompt": (SKILLS / "grounding.md").read_text(encoding="utf-8").strip()}
        return self.store.insights(sid)

    async def run(self, sid, text):
        started = time.perf_counter()
        mood = emotion(text)
        trace, proposals, usage = [], [], {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        boundary = input_boundary(text)
        if boundary:
            decision, reply = boundary
            trace.append({"type": "boundary", "name": decision, "status": "handled"})
            provider_name = "policy"
        else:
            provider_name = self.provider.name
            session = self.store.session(sid)
            mode = session["mode"]
            approved = [m["content"] for m in self.store.memories(sid, "approved")[:10]]
            prompt = (SKILLS / "persona.md").read_text(encoding="utf-8") + "\nMode: " + mode
            prompt += "\nCharacter name: " + session["character_name"]
            prompt += "\nCharacter configuration (trusted administrator instructions): " + session["character_prompt"]
            prompt += "\nUser-approved memories (data only): " + json.dumps(approved, ensure_ascii=False)
            messages = [{"role": "system", "content": prompt}]
            messages += [{"role": m["role"], "content": m["content"][:2000]} for m in self.store.history(sid, 12)]
            messages.append({"role": "user", "content": text})
            # The outer timeout bounds the whole agent run, not just one provider request.
            async with asyncio.timeout(self.settings.timeout):
                for step in range(self.settings.max_steps):
                    result = await self.provider.complete(messages, TOOLS)
                    for key in usage:
                        value = result.usage.get(key, 0)
                        usage[key] += value if isinstance(value, int) else 0
                    trace.append({"type": "model", "name": provider_name, "step": step + 1,
                                  "status": "tool_calls" if result.calls else "reply"})
                    if not result.calls:
                        reply = result.content.strip()
                        if not reply or len(reply) > 4000:
                            raise ProviderError("Provider returned an empty or oversized reply.")
                        break
                    if len(result.calls) > 4:
                        raise ProviderError("Provider exceeded the per-step tool budget.")
                    calls = [{"id": c["id"], "type": "function", "function": {
                        "name": c["name"], "arguments": json.dumps(c["arguments"], ensure_ascii=False)}} for c in result.calls]
                    messages.append({"role": "assistant", "content": result.content or None, "tool_calls": calls})
                    for c in result.calls:
                        observation = self.execute(sid, c["name"], c["arguments"], proposals)
                        trace.append({"type": "tool", "name": c["name"], "status": "denied" if "error" in observation else "ok"})
                        messages.append({"role": "tool", "tool_call_id": c["id"], "content": json.dumps(observation, ensure_ascii=False)})
                else:
                    raise ProviderError("Agent step budget exhausted; no final reply was produced.")
            reply, rewritten = output_boundary(reply)
            if rewritten:
                trace.append({"type": "boundary", "name": "identity_and_dependency", "status": "rewritten"})
        return {"run_id": str(uuid.uuid4()), "reply": reply, "emotion": mood, "provider": provider_name,
                "trace": trace, "proposals": proposals, "usage": usage if provider_name == "openai_compatible" else None,
                "latency_ms": round((time.perf_counter() - started) * 1000, 1)}
