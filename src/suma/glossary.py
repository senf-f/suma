import json
from pathlib import Path

import yaml

from suma.llm import load_question, response_text

GLOSSARY_SCHEMA = {
    "type": "object",
    "properties": {
        "terms": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "la": {"type": "string"},
                    "hr": {"type": "string"},
                    "alternatives": {"type": "array", "items": {"type": "string"}},
                    "note": {"type": "string"},
                },
                "required": ["la", "hr", "alternatives", "note"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["terms"],
    "additionalProperties": False,
}

INSTRUCTIONS = """\
Below is the Latin text of Thomas Aquinas, Summa Theologiae, as JSON units.
We are preparing a Croatian translation for educated general readers, and need a fixed
glossary so that technical terms are rendered the same way throughout.

Identify the roughly 100 recurring philosophical and theological technical terms in this text
(e.g. esse, ens, essentia, substantia, accidens, actus, potentia, forma, materia, habitus,
ratio, intellectus, causa, finis, perfectio, simplicitas, gratia). For each, give:
- la: the Latin lemma
- hr: the recommended standard Croatian equivalent, as used in Croatian neo-scholastic and
  philosophical literature where an established rendering exists
- alternatives: other plausible Croatian renderings
- note: one line explaining the choice or a distinction the translator must keep
Order terms by importance."""


def draft_glossary(latin_dir: Path, client, model: str) -> dict:
    units = []
    for path in sorted(latin_dir.glob("*/q*.json")):
        units.extend(load_question(path)["units"])
    payload = json.dumps([{"id": u["id"], "text": u["text"]} for u in units], ensure_ascii=False)

    with client.messages.stream(
        model=model,
        max_tokens=32000,
        messages=[{"role": "user", "content": f"{INSTRUCTIONS}\n\n{payload}"}],
        output_config={"effort": "high", "format": {"type": "json_schema", "schema": GLOSSARY_SCHEMA}},
    ) as stream:
        message = stream.get_final_message()

    if message.stop_reason != "end_turn":
        raise RuntimeError(f"Glossary request stopped with {message.stop_reason}")
    result = json.loads(response_text(message))
    result["usage"] = message.usage
    return result


def write_draft(terms: dict, path: Path) -> None:
    data = {"version": 1, "terms": terms["terms"]}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")


def load_glossary(path: Path) -> tuple[int, list[dict]]:
    if not path.exists():
        raise FileNotFoundError(
            "Glossary not approved: copy data/glossary.draft.yaml to data/glossary.yaml after review"
        )
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data["version"], data["terms"]
