import asyncio
import json
import time
import uuid
from pathlib import Path

from .providers import ProviderError
from .data_agent import analyze
from .safety import emotion, input_boundary, output_boundary

SKILLS = Path(__file__).parent / "skills"


def tool(name, description, properties=None, required=None):
    return {"type": "function", "function": {"name": name, "description": description,
            "parameters": {"type": "object", "properties": properties or {}, "required": required or [], "additionalProperties": False}}}


TOOLS = [
    tool("read_memories", "Read only approved memories in this session's explicitly shared memory space."),
    tool("propose_memory", "Propose a memory for user approval. This does not make it available to recall.",
         {"content": {"type": "string", "minLength": 1, "maxLength": 300}}, ["content"]),
    tool("grounding_question", "Get a short optional grounding question, not clinical advice."),
    tool("session_insights", "Read aggregate turn counts and heuristic mood labels for the current session."),
    tool("analyze_demo_data", "Execute a safe query on labeled synthetic demo analytics, never private conversations.",
         {"question": {"type": "string", "minLength": 1, "maxLength": 300}}, ["question"]),
]


class AgentFailure(ProviderError):
    def __init__(self, reason, trace, provider, latency_ms):
        super().__init__(reason)
        self.reason, self.trace, self.provider, self.latency_ms = reason, trace, provider, latency_ms


class Agent:
    def __init__(self, store, provider, settings):
        self.store, self.provider, self.settings = store, provider, settings

    def execute(self, sid, name, args, proposals):
        if name not in {t["function"]["name"] for t in TOOLS}:
            return {"error": "tool_not_allowed"}
        if not isinstance(args, dict):
            return {"error": "invalid_arguments"}
        if name == "analyze_demo_data":
            question = args.get("question")
            if set(args) != {"question"} or not isinstance(question, str) or not 1 <= len(question.strip()) <= 300:
                return {"error": "invalid_arguments"}
            try:
                return analyze(question)
            except ValueError:
                return {"error": "unsupported_or_unsafe_analysis", "scope": "synthetic demo data only"}
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

    async def run(self, sid, text, language=None):
        trace = []
        started = time.perf_counter()
        try:
            return await self._run(sid, text, language, trace)
        except (ProviderError, TimeoutError) as exc:
            reason = "run_timeout" if isinstance(exc, TimeoutError) else "provider_or_step_failure"
            trace.append({"type": "failure", "name": reason, "status": "failed"})
            raise AgentFailure(reason, trace, self.provider.name, round((time.perf_counter() - started) * 1000, 1)) from None

    async def _run(self, sid, text, language, trace):
        started = time.perf_counter()
        mood = emotion(text)
        proposals, usage = [], {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        session = self.store.session(sid)
        language = language or session.get("language", "zh")
        if language not in {"zh", "en"}:
            raise ProviderError("Unsupported language")
        boundary = input_boundary(text, language)
        if boundary:
            decision, reply = boundary
            trace.append({"type": "boundary", "name": decision, "status": "handled"})
            provider_name = "policy"
        else:
            provider_name = self.provider.name
            mode = session["mode"]
            approved = [m["content"] for m in self.store.memories(sid, "approved")[:10]]
            prompt = (SKILLS / "persona.md").read_text(encoding="utf-8") + "\nMode: " + mode
            prompt += "\nCharacter name: " + session["character_name"]
            prompt += "\nResponse language: " + language
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
                        tool_started = time.perf_counter()
                        call_proposals = list(proposals)
                        try:
                            observation = await asyncio.wait_for(asyncio.to_thread(
                                self.execute, sid, c["name"], c["arguments"], call_proposals), timeout=self.settings.tool_timeout)
                            if "error" not in observation:
                                proposals[:] = call_proposals
                        except TimeoutError:
                            observation = {"error": "tool_timeout"}
                        except Exception:
                            observation = {"error": "tool_failed"}
                        # Proposal contents stay transient; traces persist the action and consent requirement only.
                        visible_input = {"content": "[transient; confirmation required]"} if c["name"] == "propose_memory" else c["arguments"]
                        trace.append({"type": "tool", "name": c["name"], "input": visible_input, "observation": observation,
                                      "status": "denied" if "error" in observation else "ok",
                                      "duration_ms": round((time.perf_counter() - tool_started) * 1000, 1)})
                        messages.append({"role": "tool", "tool_call_id": c["id"], "content": json.dumps(observation, ensure_ascii=False)})
                else:
                    raise ProviderError("Agent step budget exhausted; no final reply was produced.")
            reply, rewritten = output_boundary(reply, language)
            if rewritten:
                trace.append({"type": "boundary", "name": "identity_and_dependency", "status": "rewritten"})
        return {"run_id": str(uuid.uuid4()), "reply": reply, "emotion": mood, "provider": provider_name,
                "trace": trace, "proposals": proposals, "usage": usage if provider_name == "openai_compatible" else None,
                "latency_ms": round((time.perf_counter() - started) * 1000, 1)}
