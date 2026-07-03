"""Event buffering and async shipping to the AgentLens server.

TODO (Week 2, docs/05-ROADMAP.md): EventBuffer (thread-safe deque), background
daemon thread flushing every ``flush_interval`` seconds or ``batch_size``
events, httpx transport with 3x exponential-backoff retries, drop-with-warning
on server unavailability, and an atexit flush hook. Design: docs/04-SDK-DESIGN.md §4.
"""
