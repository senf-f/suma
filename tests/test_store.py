import json

from suma.store import done_ids, write_units

MODEL = "claude-opus-5-5"


def test_store_merge_and_done(tmp_path):
    write_units(MODEL, "I", 2, {"I.q2.a1.obj1": "Čini se da…"}, "1", 1, tmp_path)
    write_units(MODEL, "I", 2, {"I.q2.a2.obj1": "Drugo"}, "1", 1, tmp_path)

    data = json.loads((tmp_path / MODEL / "I" / "q002.json").read_text(encoding="utf-8"))
    assert data["model"] == MODEL
    assert data["question"] == 2
    assert data["units"]["I.q2.a1.obj1"]["text"] == "Čini se da…"
    assert data["units"]["I.q2.a1.obj1"]["glossary_version"] == 1
    assert set(data["units"]) == {"I.q2.a1.obj1", "I.q2.a2.obj1"}

    assert done_ids(MODEL, "1", 1, tmp_path) == {"I.q2.a1.obj1", "I.q2.a2.obj1"}
    assert done_ids(MODEL, "1", 2, tmp_path) == set()
    assert done_ids(MODEL, "2", 1, tmp_path) == set()
    assert done_ids("claude-sonnet-5-5", "1", 1, tmp_path) == set()


def test_store_overwrites_retranslated_unit(tmp_path):
    write_units(MODEL, "I", 2, {"I.q2.pr": "staro"}, "1", 1, tmp_path)
    write_units(MODEL, "I", 2, {"I.q2.pr": "novo"}, "1", 2, tmp_path)

    data = json.loads((tmp_path / MODEL / "I" / "q002.json").read_text(encoding="utf-8"))
    assert data["units"]["I.q2.pr"]["text"] == "novo"
    assert data["units"]["I.q2.pr"]["glossary_version"] == 2
