"""Deterministic replay client — mock-mode execution of recorded runs.

TODO (Week 10, docs/05-ROADMAP.md): ``agentlens.replay(run_id, mode="mock")``
fetches the run's stored LLM calls, loads them into an ordered queue, and
flips the patchers into mock mode so clients serve stored responses in call
order (fallback match: model + message hash). Design: docs/04-SDK-DESIGN.md §7.
"""
