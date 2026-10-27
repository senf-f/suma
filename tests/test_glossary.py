import json

import pytest

from fakes import FakeClient, message
from suma.glossary import GLOSSARY_SCHEMA, draft_glossary, load_glossary, write_draft

TERMS = {
    "terms": [
        {"la": "esse", "hr": "bitak", "alternatives": ["biti", "postojanje"], "note": "čin postojanja"},
        {"la": "actus", "hr": "zbiljnost", "alternatives": ["čin"], "note": "nasuprot mogućnosti"},
    ]
}


@pytest.fixture
def latin_dir(tmp_path):
    q = {"id": "I.q2", "part": "I", "question": 2,
         "units": [{"id": "I.q2.pr", "kind": "pr", "text": "Quia igitur principalis intentio"}]}
    (tmp_path / "I").mkdir()
    (tmp_path / "I" / "q002.json").write_text(json.dumps(q), encoding="utf-8")
    return tmp_path


def test_draft_parses_terms(latin_dir):
    client = FakeClient(message(TERMS))

    result = draft_glossary(latin_dir, client, "claude-opus-5-5")

    assert [t["la"] for t in result["terms"]] == ["esse", "actus"]
    [call] = client.messages.calls
    assert call["model"] == "claude-opus-5-5"
    assert call["output_config"]["format"] == {"type": "json_schema", "schema": GLOSSARY_SCHEMA}
    assert "Quia igitur principalis intentio" in json.dumps(call["messages"], ensure_ascii=False)


def test_draft_raises_on_refusal(latin_dir):
    client = FakeClient(message(stop_reason="refusal", text=""))

    with pytest.raises(RuntimeError, match="refusal"):
        draft_glossary(latin_dir, client, "claude-opus-5-5")


def test_yaml_roundtrip_utf8(tmp_path):
    path = tmp_path / "glossary.draft.yaml"
    write_draft(TERMS, path)

    version, terms = load_glossary(path)

    assert version == 1
    assert terms[0]["hr"] == "bitak"
    assert terms[0]["note"] == "čin postojanja"
    assert terms[1]["hr"] == "zbiljnost"
    assert "čin" in path.read_text(encoding="utf-8")


def test_missing_glossary_message(tmp_path):
    with pytest.raises(FileNotFoundError, match="Glossary not approved"):
        load_glossary(tmp_path / "glossary.yaml")
