import asyncio
import json
import time
import uuid
from pathlib import Path

from .providers import ProviderError
from .data_agent import analyze
from .safety import emotion, input_boundary, output_boundary
from .context import ContextBuilder, profile_for_prompt, byte_size

SKILLS = Path(__file__).parent / "skills"


def tool(name, description, properties=None, required=None):
    return {"type": "function", "function": {"name": name, "description": description,
            "parameters": {"type": "object", "properties": properties or {}, "required": required or [], "additionalProperties": False}}}


TOOLS = [
    tool("read_own_profile", "Read this session's frozen fictional adult character profile; never the user's identity or another character."),
    tool("read_memories", "Read only approved memories in this session's explicitly shared memory space."),
    tool("propose_memory", "Propose a memory for user approval. This does not make it available to recall.",
         {"content": {"type": "string", "minLength": 1, "maxLength": 300}}, ["content"]),
    tool("grounding_question", "Get a short optional grounding question, not clinical advice."),
    tool("session_insights", "Read aggregate turn counts and heuristic mood labels for the current session."),
    tool("analyze_demo_data", "Execute a safe query on labeled synthetic demo analytics, never private conversations.",
         {"question": {"type": "string", "minLength": 1, "maxLength": 300}}, ["question"]),
]


class AgentFailure(ProviderError):
    def __init__(self, reason, trace, provider, latency_ms, metadata=None):
        super().__init__(reason, metadata)
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
        if name == "read_own_profile":
            return self.store.session_profile(sid)
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
            raise AgentFailure(reason, trace, self.provider.name, round((time.perf_counter() - started) * 1000, 1),
                               getattr(exc, "metadata", {})) from None

    async def _run(self, sid, text, language, trace):
        started = time.perf_counter()
        mood = emotion(text)
        proposals, usage = [], {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        session = self.store.session(sid)
        if not session:
            raise ProviderError("Session not found")
        language = language or session.get("language", "zh")
        if language not in {"zh", "en"}:
            raise ProviderError("Unsupported language")
        boundary = input_boundary(text, language, session["character_id"])
        completion_status = "complete"
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
            profile = self.store.session_profile(sid)
            prompt += "\n<FROZEN_FICTIONAL_CHARACTER_PROFILE>\n" + json.dumps(profile_for_prompt(profile, language), ensure_ascii=False) + "\n</FROZEN_FICTIONAL_CHARACTER_PROFILE>"
            prompt += "\n<USER_APPROVED_MEMORY_DATA>\n" + json.dumps(approved, ensure_ascii=False) + "\n</USER_APPROVED_MEMORY_DATA>"
            try:
                summary, recent, context_metrics = ContextBuilder(self.store).build(sid)
            except ValueError:
                raise ProviderError("Session not found") from None
            prompt += "\n<UNTRUSTED_SESSION_EXCERPTS>\n" + json.dumps(summary, ensure_ascii=False) + "\n</UNTRUSTED_SESSION_EXCERPTS>"
            messages = [{"role": "system", "content": prompt}]
            messages += recent
            messages.append({"role": "user", "content": text})
            trace.append({"type": "context", "name": "extractive_session_context", "status": "lossy" if context_metrics["lossy"] else "included",
                          "observation": context_metrics})
            # The outer timeout bounds the whole agent run, not just one provider request.
            async with asyncio.timeout(self.settings.timeout):
                for step in range(self.settings.max_steps):
                    current = self.store.session(sid)
                    if not current or current.get("owner_user_id") != session.get("owner_user_id"):
                        raise ProviderError("Session is no longer available")
                    # Conservative byte budget, not a tokenizer or a provider-window claim.
                    if byte_size(json.dumps(messages, ensure_ascii=False)) > 120000:
                        raise ProviderError("Context budget exceeded; shorten the current conversation or profile.")
                    result = await self.provider.complete(messages, TOOLS)
                    for key in usage:
                        value = result.usage.get(key, 0)
                        usage[key] += value if isinstance(value, int) else 0
                    trace.append({"type": "model", "name": provider_name, "step": step + 1,
                                  "status": "tool_calls" if result.calls else "reply",
                                  "finish_reason": result.metadata.get("finish_reason", "not reported")})
                    if not result.calls:
                        reply = result.content.strip()
                        if not reply or len(reply) > 8000:
                            raise ProviderError("Provider returned an empty or oversized reply.")
                        if result.metadata.get("truncated"):
                            completion_status = "truncated"
                            proposals.clear()
                            trace.append({"type": "completion", "name": "output_budget", "status": "truncated"})
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
            reply, rewritten = output_boundary(reply, language, session["character_id"])
            if rewritten:
                trace.append({"type": "boundary", "name": "identity_and_dependency", "status": "rewritten"})
            if completion_status == "truncated":
                reply += ("\n\n[本条回复达到长度上限，可能未说完；你可以让我继续。未自动续写。]" if language == "zh" else
                          "\n\n[This reply reached its length limit and may be incomplete. You can ask me to continue; no automatic continuation was sent.]")
        return {"run_id": str(uuid.uuid4()), "reply": reply, "emotion": mood, "provider": provider_name,
                "completion_status": completion_status,
                "trace": trace, "proposals": proposals, "usage": usage if provider_name == "openai_compatible" else None,
                "latency_ms": round((time.perf_counter() - started) * 1000, 1)}
