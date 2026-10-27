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


def succeeded(custom_id, msg):
    return SimpleNamespace(custom_id=custom_id, result=SimpleNamespace(type="succeeded", message=msg))


def errored(custom_id):
    error = SimpleNamespace(type="error", error=SimpleNamespace(type="overloaded_error", message="overloaded"))
    return SimpleNamespace(custom_id=custom_id, result=SimpleNamespace(type="errored", error=error))


class FakeBatches:
    def __init__(self, respond, polls_before_end=1):
        self.respond = respond
        self.polls_before_end = polls_before_end
        self.created = []
        self._polls = 0

    def create(self, requests):
        self.created.append(requests)
        return SimpleNamespace(id=f"msgbatch_{len(self.created)}", processing_status="in_progress")

    def retrieve(self, batch_id):
        self._polls += 1
        status = "ended" if self._polls > self.polls_before_end else "in_progress"
        return SimpleNamespace(id=batch_id, processing_status=status)

    def results(self, batch_id):
        return self.respond(self.created[-1])


class FakeBatchClient:
    """respond(requests) -> list of batch result entries for the last created batch."""

    def __init__(self, respond, input_tokens=1000):
        self.messages = SimpleNamespace(
            batches=FakeBatches(respond),
            count_tokens=lambda **kwargs: SimpleNamespace(input_tokens=input_tokens),
        )
