"""Auto-tracing patch for the Anthropic client.

TODO (Week 3, docs/05-ROADMAP.md): wrap
``anthropic.resources.messages.Messages.create`` to record model, messages,
params, tokens, finish reason, latency, and errors as an LLM span. Pattern:
docs/04-SDK-DESIGN.md §6. Streaming is a V1 punt (single span finalized on
stream close, M3 if time allows).
"""
