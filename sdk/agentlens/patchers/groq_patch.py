"""Auto-tracing patch for the Groq (OpenAI-compatible) client.

TODO (Week 3, docs/05-ROADMAP.md): analogous to anthropic_patch — wrap the
chat completions create method to record model, messages, params, tokens,
finish reason, latency, and errors as an LLM span.
"""
