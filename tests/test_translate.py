import json
import shutil

import pytest

from fakes import FakeBatchClient, errored, message, succeeded
from suma.glossary import write_draft
from suma.prompt import request_unit_ids
from suma.translate import estimate_cost, run_translate

MODEL = "claude-opus-5-5"


@pytest.fixture
def data_dir(latin_q2, tmp_path):
    data = tmp_path / "data"
    shutil.copytree(latin_q2, data / "latin")
    write_draft({"terms": [{"la": "esse", "hr": "bitak", "alternatives": [], "note": ""}]}, data / "glossary.yaml")
    return data


def translate_all(requests):
    return [
        succeeded(r["custom_id"], message({"units": [{"id": i, "text": f"HR {i}"} for i in request_unit_ids(r)]}))
        for r in requests
    ]


def stored_units(data_dir):
    path = data_dir / "hr" / MODEL / "I" / "q002.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))["units"]


def run(client, data_dir, **kwargs):
    kwargs.setdefault("yes", True)
    return run_translate("I.q1-13", "opus", client, data_dir=data_dir, poll_seconds=0, sleep=lambda s: None, **kwargs)


def test_aborts_without_confirmation(data_dir):
    client = FakeBatchClient(translate_all)

    summary = run(client, data_dir, yes=False, input_fn=lambda prompt: "n")

    assert client.messages.batches.created == []
    assert summary.written == 0


def test_happy_path_writes_units(data_dir):
    client = FakeBatchClient(translate_all)

    summary = run(client, data_dir, yes=False, input_fn=lambda prompt: "y")

    assert summary.failed == []
    assert summary.written == 7
    units = stored_units(data_dir)
    assert units["I.q2.a3.resp"]["text"] == "HR I.q2.a3.resp"
    assert units["I.q2.a3.resp"]["glossary_version"] == 1
    saved = json.loads((data_dir / "batches" / "msgbatch_1.json").read_text(encoding="utf-8"))
    assert saved["model"] == MODEL
    assert saved["expected"]["I-q2-pr"] == ["I.q2.pr"]


def missing_id_reply(requests):
    by_id = {r["custom_id"]: r for r in requests}
    a3_ids = request_unit_ids(by_id["I-q2-a3"])
    partial = message({"units": [{"id": i, "text": "x"} for i in a3_ids[:-1]]})
    return [errored("I-q2-pr"), succeeded("I-q2-a3", partial)]


def test_mixed_results_write_nothing_for_failures(data_dir):
    client = FakeBatchClient(missing_id_reply)

    summary = run(client, data_dir)

    assert summary.written == 0
    assert sorted(cid for cid, _ in summary.failed) == ["I-q2-a3", "I-q2-pr"]
    assert any("missing" in reason for _, reason in summary.failed)
    assert stored_units(data_dir) == {}


def test_rerun_only_missing(data_dir):
    run(FakeBatchClient(missing_id_reply), data_dir)
    first_ok = FakeBatchClient(lambda reqs: [r for r in translate_all(reqs) if r.custom_id == "I-q2-pr"]
                               + [errored("I-q2-a3")])
    run(first_ok, data_dir)

    retry = FakeBatchClient(translate_all)
    summary = run(retry, data_dir)

    [created] = retry.messages.batches.created
    assert [r["custom_id"] for r in created] == ["I-q2-a3"]
    assert summary.failed == []
    assert len(stored_units(data_dir)) == 7


def test_nothing_to_do_submits_nothing(data_dir):
    run(FakeBatchClient(translate_all), data_dir)
    again = FakeBatchClient(translate_all)

    summary = run(again, data_dir)

    assert again.messages.batches.created == []
    assert summary.written == 0


def test_collect_handles_multi_part_ids(data_dir):
    q90 = {"id": "I-II.q90", "part": "I-II", "question": 90,
           "units": [{"id": "I-II.q90.a4.resp", "kind": "resp", "text": "Respondeo dicendum quod lex"}]}
    (data_dir / "latin" / "I-II").mkdir()
    (data_dir / "latin" / "I-II" / "q090.json").write_text(json.dumps(q90), encoding="utf-8")

    summary = run_translate("I-II.q90", "opus", FakeBatchClient(translate_all), yes=True,
                            data_dir=data_dir, poll_seconds=0, sleep=lambda s: None)

    assert summary.failed == []
    stored = json.loads((data_dir / "hr" / MODEL / "I-II" / "q090.json").read_text(encoding="utf-8"))
    assert stored["units"]["I-II.q90.a4.resp"]["text"] == "HR I-II.q90.a4.resp"


def test_refuses_resubmit_while_batch_uncollected(data_dir):
    class Interrupted(Exception):
        pass

    def interrupt(seconds):
        raise Interrupted

    stuck = FakeBatchClient(translate_all)
    stuck.messages.batches.polls_before_end = 5
    with pytest.raises(Interrupted):
        run_translate("I.q1-13", "opus", stuck, yes=True, data_dir=data_dir, poll_seconds=0, sleep=interrupt)

    again = FakeBatchClient(translate_all)
    with pytest.raises(RuntimeError, match="--collect msgbatch_1"):
        run(again, data_dir)
    assert again.messages.batches.created == []


def test_collected_batch_allows_new_submission(data_dir):
    run(FakeBatchClient(missing_id_reply), data_dir)

    retry = FakeBatchClient(translate_all)
    run(retry, data_dir)

    assert len(retry.messages.batches.created) == 1


def test_estimate_applies_batch_discount():
    request = {"params": {"model": MODEL, "system": [], "messages": [{"role": "user", "content": "x:\n[]"}]}}
    client = FakeBatchClient(translate_all, input_tokens=1_000_000)

    input_tokens, output_tokens, usd = estimate_cost([request], client, MODEL)

    assert (input_tokens, output_tokens) == (1_000_000, 0)
    assert usd == pytest.approx(2.0)
