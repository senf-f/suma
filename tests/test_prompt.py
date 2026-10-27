import json
import re

import pytest

from fakes import message
from suma.prompt import TranslationError, build_requests, system_prompt, validate

GLOSSARY = (1, [{"la": "esse", "hr": "bitak", "alternatives": ["biti"], "note": "čin postojanja"}])
A3_IDS = ["I.q2.a3.obj1", "I.q2.a3.obj2", "I.q2.a3.sc", "I.q2.a3.resp", "I.q2.a3.ad1", "I.q2.a3.ad2"]


def files(latin_dir):
    return sorted(latin_dir.glob("I/q*.json"))


def test_build_requests_groups_by_article(latin_q2):
    requests = build_requests(files(latin_q2), "claude-opus-5-5", GLOSSARY, done=set())

    assert [r["custom_id"] for r in requests] == ["I-q2-pr", "I-q2-a3"]
    for r in requests:
        assert re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", r["custom_id"])
        params = r["params"]
        assert params["model"] == "claude-opus-5-5"
        assert params["system"][0]["cache_control"] == {"type": "ephemeral"}
        assert params["output_config"]["format"]["type"] == "json_schema"
    user = requests[1]["params"]["messages"][0]["content"]
    assert [u["id"] for u in json.loads(user[user.index("["):])] == A3_IDS


def test_build_requests_skips_done(latin_q2):
    requests = build_requests(files(latin_q2), "claude-opus-5-5", GLOSSARY, done=set(A3_IDS))

    assert [r["custom_id"] for r in requests] == ["I-q2-pr"]


def test_build_requests_sends_only_missing_units(latin_q2):
    requests = build_requests(files(latin_q2), "claude-opus-5-5", GLOSSARY, done=set(A3_IDS[:4]))

    user = requests[1]["params"]["messages"][0]["content"]
    assert [u["id"] for u in json.loads(user[user.index("["):])] == A3_IDS[4:]


def test_system_prompt_contains_glossary():
    prompt = system_prompt(GLOSSARY[1])
    assert "esse → bitak" in prompt
    assert "*" in prompt


def reply(units):
    return message({"units": [{"id": i, "text": t} for i, t in units]})


def test_validate_ok():
    assert validate(["a", "b"], reply([("b", "dva"), ("a", "jedan")])) == {"a": "jedan", "b": "dva"}


def test_validate_missing_id():
    with pytest.raises(TranslationError, match="missing"):
        validate(["a", "b"], reply([("a", "jedan")]))


def test_validate_extra_id():
    with pytest.raises(TranslationError, match="unexpected"):
        validate(["a"], reply([("a", "jedan"), ("z", "x")]))


def test_validate_duplicate_id():
    with pytest.raises(TranslationError, match="duplicate"):
        validate(["a"], reply([("a", "jedan"), ("a", "opet")]))


def test_validate_empty_text():
    with pytest.raises(TranslationError, match="empty"):
        validate(["a"], reply([("a", "   ")]))


def test_validate_bad_json():
    with pytest.raises(TranslationError, match="JSON"):
        validate(["a"], message(text='{"units": [ broken'))


def test_validate_refusal():
    with pytest.raises(TranslationError, match="refusal"):
        validate(["a"], message(stop_reason="refusal", text=""))


def test_validate_max_tokens():
    with pytest.raises(TranslationError, match="max_tokens"):
        validate(["a"], message(stop_reason="max_tokens", text='{"units": ['))
