import json

MODELS = {"opus": "claude-opus-5-5", "sonnet": "claude-sonnet-5-5", "haiku": "claude-haiku-5-5"}

# USD per million tokens (input, output), standard rates before the 50% batch discount.
# Haiku 5.5 rate holds for prompts up to 100K tokens; our per-article requests stay far below that.
PRICES = {"claude-opus-5-5": (4.0, 20.0), "claude-sonnet-5-5": (2.0, 10.0), "claude-haiku-5-5": (0.10, 0.50)}


def response_text(message) -> str:
    return next(block.text for block in message.content if block.type == "text")


def usage_cost(model: str, input_tokens: int, output_tokens: int, batch: bool = False) -> float:
    price_in, price_out = PRICES[model]
    usd = (input_tokens * price_in + output_tokens * price_out) / 1_000_000
    return usd / 2 if batch else usd


def message_cost(model: str, usage, batch: bool = False) -> float:
    price_in, price_out = PRICES[model]
    cache_write = getattr(usage, "cache_creation_input_tokens", 0) or 0
    cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
    usd = (
        usage.input_tokens * price_in
        + cache_write * price_in * 1.25
        + cache_read * price_in * 0.1
        + usage.output_tokens * price_out
    ) / 1_000_000
    return usd / 2 if batch else usd


def load_question(path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))
