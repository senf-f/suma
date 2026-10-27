from types import SimpleNamespace

import pytest

from suma.llm import message_cost


def test_message_cost_counts_cache_tokens():
    usage = SimpleNamespace(
        input_tokens=1_000_000,
        output_tokens=1_000_000,
        cache_creation_input_tokens=1_000_000,
        cache_read_input_tokens=1_000_000,
    )
    # Opus 5.5: 4 + 20 + 4*1.25 + 4*0.1 = 29.4 standard; batch halves it.
    assert message_cost("claude-opus-5-5", usage) == pytest.approx(29.4)
    assert message_cost("claude-opus-5-5", usage, batch=True) == pytest.approx(14.7)


def test_message_cost_tolerates_missing_cache_fields():
    usage = SimpleNamespace(input_tokens=1_000_000, output_tokens=0)
    assert message_cost("claude-sonnet-5-5", usage) == pytest.approx(2.0)
