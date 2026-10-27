import json

MODELS = {"opus": "claude-opus-5-5", "sonnet": "claude-sonnet-5-5"}

# USD per million tokens (input, output), standard rates before the 50% batch discount.
PRICES = {"claude-opus-5-5": (4.0, 20.0), "claude-sonnet-5-5": (2.0, 10.0)}


def response_text(message) -> str:
    return next(block.text for block in message.content if block.type == "text")


def usage_cost(model: str, input_tokens: int, output_tokens: int, batch: bool = False) -> float:
    price_in, price_out = PRICES[model]
    usd = (input_tokens * price_in + output_tokens * price_out) / 1_000_000
    return usd / 2 if batch else usd


def load_question(path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))
