import json
from types import SimpleNamespace


def message(payload=None, stop_reason="end_turn", text=None, input_tokens=100, output_tokens=50):
    body = text if text is not None else json.dumps(payload, ensure_ascii=False)
    return SimpleNamespace(
        stop_reason=stop_reason,
        content=[SimpleNamespace(type="thinking", thinking=""), SimpleNamespace(type="text", text=body)],
        usage=SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens),
    )


class _Stream:
    def __init__(self, msg):
        self._msg = msg

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get_final_message(self):
        return self._msg


class FakeMessages:
    def __init__(self, reply=None):
        self.reply = reply
        self.calls = []

    def stream(self, **kwargs):
        self.calls.append(kwargs)
        return _Stream(self.reply)


class FakeClient:
    def __init__(self, reply=None):
        self.messages = FakeMessages(reply)
