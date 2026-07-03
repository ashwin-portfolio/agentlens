# AgentLens — Python SDK Design (V1)

Package name: `agentlens` (PyPI) · Python ≥3.10 · Zero heavy dependencies (httpx only).

## 1. Developer Experience Target

Integration in ≤3 lines — this is goal G1 and the README's first code block:

```python
import agentlens

agentlens.init(api_key="al_...", project="fittrack-recipes",
               endpoint="https://lens.myserver.com")  # 1

@agentlens.trace(name="generate_recipe", span_type="agent")   # 2
def generate_recipe(user_profile: dict) -> dict:
    ...

agentlens.patch_anthropic()  # 3 — every Anthropic call now auto-traced
```

## 2. Public API Surface (keep it this small)

```python
# lifecycle
agentlens.init(api_key, project, endpoint, *, flush_interval=2.0,
               batch_size=50, disabled=False)
agentlens.flush()      # force-ship buffered events (call before process exit)
agentlens.shutdown()

# tracing
@agentlens.trace(name=None, span_type="function", tags=None, capture_args=True)
# - works on sync and async functions
# - name defaults to function __qualname__
# - span_type: "agent" | "function" | "tool"

with agentlens.span(name, span_type="function", input=None) as sp:
    sp.set_output(...)          # manual spans for non-function work
    sp.set_metadata(key=value)

agentlens.run(name, tags=None, metadata=None)   # context manager creating a Run
# If @trace fires with no active run, an implicit run is auto-created.

# provider auto-patching
agentlens.patch_anthropic()   # wraps anthropic.Anthropic().messages.create
agentlens.patch_groq()        # wraps OpenAI-compatible groq client

# replay
agentlens.replay(run_id, mode="mock")  # returns a context; inside it, patched
                                        # clients serve stored responses in order
```

## 3. Usage — multi-agent example

```python
with agentlens.run("recipe_pipeline", tags={"env": "prod"}):
    plan   = planner_agent(profile)      # @trace(span_type="agent")
    recipe = recipe_agent(plan)          # @trace(span_type="agent")
    check  = nutrition_check(recipe)     # @trace(span_type="tool")
# → one Run, three agent/tool spans, LLM-call spans nested under each (via patchers)
```

## 4. Internal Architecture

```
@trace / span() / run()
        │  (creates SpanContext, reads parent from contextvars)
        ▼
  EventBuffer (thread-safe deque)
        │  background daemon thread
        │  flush: every 2s OR 50 events OR explicit flush()
        ▼
  Transport (httpx) ── POST /v1/ingest ── retry 3x exp backoff ── drop + warn
```

Rules:
- **Never raise into user code.** All SDK exceptions are caught, logged via `logging.getLogger("agentlens")`, swallowed.
- **Never block.** Event creation is an O(1) append; network happens only on the background thread.
- `disabled=True` (or env `AGENTLENS_DISABLED=1`) turns everything into no-ops — for tests.
- `atexit` hook calls `flush()` so short scripts don't lose events.

## 5. Context Propagation

```python
# context.py
from contextvars import ContextVar

current_run:  ContextVar[RunContext | None]  = ContextVar("al_run",  default=None)
current_span: ContextVar[SpanContext | None] = ContextVar("al_span", default=None)
```

`@trace` entry: `parent = current_span.get()` → new span with `parent_span_id=parent.id`
→ `token = current_span.set(new)` → on exit `current_span.reset(token)`.
contextvars makes this correct under asyncio and threads without any user effort.

## 6. Anthropic Patcher (pattern; Groq is analogous)

```python
# patchers/anthropic_patch.py
def patch_anthropic():
    import anthropic
    original = anthropic.resources.messages.Messages.create

    def traced_create(self, *args, **kwargs):
        span = _start_llm_span(provider="anthropic",
                               model=kwargs.get("model"),
                               messages=kwargs.get("messages"),
                               params=_pick(kwargs, "max_tokens", "temperature", "system"))
        t0 = time.perf_counter()
        try:
            resp = original(self, *args, **kwargs)
        except Exception as e:
            span.fail(error=repr(e)); raise
        span.finish(response_content=[b.model_dump() for b in resp.content],
                    finish_reason=resp.stop_reason,
                    input_tokens=resp.usage.input_tokens,
                    output_tokens=resp.usage.output_tokens,
                    latency_s=time.perf_counter() - t0)
        return resp

    anthropic.resources.messages.Messages.create = traced_create
```

V1 punt: streaming responses — record them as a single span finalized when the
stream closes (implement in M3 if time allows; document as roadmap otherwise).

## 7. Replay Client (D4 — the differentiator)

```python
with agentlens.replay(run_id="...", mode="mock"):
    generate_recipe(same_input)
# Patched clients now return the STORED responses for that run, matched by
# call order (fallback: match on model + message hash). No tokens spent.
# Perfect for stepping through a production failure in a debugger.
```

Implementation: `replay()` fetches the run's LLM calls from the server, loads
them into an ordered queue, and flips the patchers into mock mode for the
duration of the context.

## 8. Testing Strategy (SDK)
- Unit: decorator nesting produces correct parent/child ids (contextvars under asyncio).
- Unit: buffer flush triggers (time, size, atexit); server-down → retries → drop without raising.
- Integration: fake FastAPI ingest endpoint asserts batched payload shape.
- E2E: examples/quickstart.py against docker-compose stack.

## 9. Packaging
- `pyproject.toml` (hatchling), version 0.1.0, MIT.
- `pip install agentlens` must work with only `httpx` pulled in.
- Publish in M3 — a PyPI package on the resume signals "ships real software."
