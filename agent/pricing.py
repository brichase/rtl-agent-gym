"""Model pricing used for episode cost accounting.

Rates are deliberately unset until the campaign conductor verifies the published
claude-opus-5 prices.  Missing rates produce a JSON null cost rather than a guess.
"""

from __future__ import annotations


PRICING: dict[str, dict[str, float | None]] = {
    "claude-opus-5": {
        "input_per_million_usd": None,  # TODO: verify current published rate.
        "output_per_million_usd": None,  # TODO: verify current published rate.
    }
}


def calculate_cost(model_id: str, tokens_in: int, tokens_out: int) -> float | None:
    rates = PRICING.get(model_id)
    if not rates:
        return None
    input_rate = rates.get("input_per_million_usd")
    output_rate = rates.get("output_per_million_usd")
    if input_rate is None or output_rate is None:
        return None
    return (tokens_in * input_rate + tokens_out * output_rate) / 1_000_000
