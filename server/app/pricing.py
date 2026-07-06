"""Per-model pricing (USD per 1M tokens), applied server-side at ingestion.

Per docs/02-ARCHITECTURE.md D3: prices are illustrative and change over time —
update this table to update all future cost computation. Historical rows keep
the cost_usd computed at their ingestion time.
"""

from decimal import Decimal

# model -> (input USD per 1M tokens, output USD per 1M tokens)
PRICING: dict[str, tuple[Decimal, Decimal]] = {
    "claude-sonnet-4-6": (Decimal("3.00"), Decimal("15.00")),
    "claude-haiku-4-5-20251001": (Decimal("1.00"), Decimal("5.00")),
    "llama-3.3-70b-versatile": (Decimal("0.59"), Decimal("0.79")),
}

_ONE_MILLION = Decimal("1000000")


class UnknownModelError(ValueError):
    def __init__(self, model: str) -> None:
        super().__init__(
            f"No pricing entry for model {model!r}; add it to app/pricing.py PRICING"
        )
        self.model = model


def compute_cost(model: str, input_tokens: int, output_tokens: int) -> Decimal:
    try:
        input_price, output_price = PRICING[model]
    except KeyError:
        raise UnknownModelError(model) from None
    return (
        input_tokens * input_price / _ONE_MILLION
        + output_tokens * output_price / _ONE_MILLION
    )
