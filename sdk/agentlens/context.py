"""contextvars-based run/span propagation for automatic trace-tree nesting.

TODO (Week 2, docs/05-ROADMAP.md): ``current_run`` and ``current_span``
ContextVars per docs/04-SDK-DESIGN.md §5; ``@trace`` reads the current span as
parent, sets itself, and restores on exit — correct under asyncio and threads.
"""
