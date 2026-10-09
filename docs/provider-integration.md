# Provider integration checklist

On 2026-10-09 the owner identified the supplied server-side key as an official DeepSeek key. The ignored `.env` was configured with the documented official base URL and `deepseek-flash`; eight synthetic scenarios produced ten actual model requests with no execution failures. See [DeepSeek setup](deepseek.md) and [recorded evidence](evidence/live-deepseek-2026-10-09.json). Human companion-quality scoring is pending. No provider destination was inferred from a key's shape.

1. Choose an OpenAI-compatible Chat Completions endpoint with function-tool support.
2. Put the base URL, model, and key in local `.env`; never enter the key into the UI, an issue, or the repository.
3. Set `HARBOR_PROVIDER=openai_compatible` and restart the backend.
4. Check `/api/status`: provider, configured flag, and model must be truthful.
5. Try a normal turn, a memory-read tool call, and a memory proposal; approve the proposal manually.
6. Verify an intentional timeout/invalid credential fails visibly rather than returning mock content.
7. Record model/provider, prompt version, date, sample scope, latency, token usage when supplied, failures, and human quality reviews.

The entire loop has a deadline and a step budget. The provider response must contain a nonempty final reply or valid tool calls. The exact official DeepSeek host uses `max_tokens=600` and disabled thinking; other compatible hosts retain `max_completion_tokens=600`. Truncation, filtering, refusal and malformed responses fail visibly. Hidden reasoning is discarded. The adapter does not assume streaming support and does not support every vendor-specific extension.

Automatic conversation here means generating responses within this app after a user sends a message. No WeChat/HR account integration, proactive messaging, or background social outreach is included.

All real-provider messages and approved memory in the request are transmitted to that provider. Keep eval data synthetic until a deliberate consent and retention workflow is ready.
