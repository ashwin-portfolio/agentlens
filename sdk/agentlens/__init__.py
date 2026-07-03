"""AgentLens Python SDK.

Trace every step, score every output, replay every failure.

Public API surface is defined in docs/04-SDK-DESIGN.md §2. Phase 0 ships a
package skeleton only; ``trace``, ``span``, ``run``, the provider patchers,
and ``replay`` land in roadmap Weeks 2-3 and 10 (docs/05-ROADMAP.md).
"""

from __future__ import annotations

__version__ = "0.1.0"

__all__ = ["init"]


def init(
    api_key: str | None = None,
    project: str | None = None,
    endpoint: str | None = None,
    *,
    flush_interval: float = 2.0,
    batch_size: int = 50,
    disabled: bool = False,
) -> None:
    """Configure the AgentLens SDK for the current process.

    No-op stub. The real implementation (event buffer, background shipper,
    retries) is roadmap Week 2 — see docs/05-ROADMAP.md and
    docs/04-SDK-DESIGN.md §4.

    Args:
        api_key: Project API key (``al_...``).
        project: Project name events are recorded under.
        endpoint: Base URL of the AgentLens server.
        flush_interval: Seconds between background flushes of buffered events.
        batch_size: Flush when this many events are buffered.
        disabled: Turn the whole SDK into no-ops (also via ``AGENTLENS_DISABLED=1``).
    """
    return None
