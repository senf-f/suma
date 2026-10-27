import json
from pathlib import Path

from suma.ids import article_of, custom_id
from suma.llm import load_question, response_text

PROMPT_VERSION = "1"

TRANSLATION_SCHEMA = {
    "type": "object",
    "properties": {
        "units": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"id": {"type": "string"}, "text": {"type": "string"}},
                "required": ["id", "text"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["units"],
    "additionalProperties": False,
}

STYLE_GUIDE = """\
You translate Thomas Aquinas, Summa Theologiae, from Latin into Croatian.

Audience and register
- Standard Croatian (ijekavian, current orthography) for educated general readers:
  students, clergy and interested laypeople.
- Faithful to the argument, but readable: split very long Latin periods into several
  sentences where that helps, without dropping or adding content.

Fixed scholastic formulas (use them consistently)
- "Ad primum sic proceditur. Videtur quod ..." -> "Na prvo se ovako postupa. Čini se da ..."
  (likewise "Ad secundum/tertium ..." -> "Na drugo/treće ...")
- "Praeterea" -> "Osim toga"
- "Sed contra" -> "Ali protiv toga"
- "Respondeo dicendum quod" -> "Odgovaram: treba reći da"
- "Ad primum ergo dicendum quod" -> "Na prvo, dakle, treba reći da"
  (likewise "Ad secundum/tertium dicendum" -> "Na drugo/treće treba reći da")

Terminology
- Always render glossary terms with the given Croatian term (Latin → Croatian below),
  inflected as grammar requires. Do not substitute a synonym.

Quotations and references
- Scripture and other authorities are quoted from the Latin as Aquinas gives it: translate
  that Latin directly, do not substitute a modern Croatian Bible text.
- Keep references (book, chapter, author) and render book names in standard Croatian form.
- Text between asterisks (*like this*) marks a quotation: keep the asterisks around the
  translated quotation.

Output
- Return every unit ID you are given exactly once, with its Croatian text, and nothing else.

Glossary
"""


class TranslationError(Exception):
    pass


def system_prompt(glossary_terms: list[dict]) -> str:
    lines = [f"- {t['la']} → {t['hr']}" + (f" ({t['note']})" if t.get("note") else "") for t in glossary_terms]
    return STYLE_GUIDE + "\n".join(lines)


def build_requests(
    latin_files: list[Path], model: str, glossary: tuple[int, list[dict]], done: set[str]
) -> list[dict]:
    system = [{"type": "text", "text": system_prompt(glossary[1]), "cache_control": {"type": "ephemeral"}}]
    requests = []
    for path in latin_files:
        question = load_question(path)
        articles: dict[str, list[dict]] = {}
        for unit in question["units"]:
            if unit["id"] not in done:
                articles.setdefault(article_of(unit["id"]), []).append({"id": unit["id"], "text": unit["text"]})
        for article_id, units in articles.items():
            content = (
                f"Question {question['id']}, {article_id}. Translate these units into Croatian:\n"
                + json.dumps(units, ensure_ascii=False, indent=1)
            )
            requests.append({
                "custom_id": custom_id(article_id),
                "params": {
                    "model": model,
                    "max_tokens": 32000,
                    "system": system,
                    "messages": [{"role": "user", "content": content}],
                    "output_config": {
                        "effort": "medium",
                        "format": {"type": "json_schema", "schema": TRANSLATION_SCHEMA},
                    },
                },
            })
    return requests


def request_units(request: dict) -> list[dict]:
    content = request["params"]["messages"][0]["content"]
    return json.loads(content[content.index("["):])


def request_unit_ids(request: dict) -> list[str]:
    return [u["id"] for u in request_units(request)]


def validate(expected_ids: list[str], message) -> dict[str, str]:
    if message.stop_reason != "end_turn":
        raise TranslationError(f"stopped with {message.stop_reason}")
    try:
        units = json.loads(response_text(message))["units"]
    except (json.JSONDecodeError, KeyError, StopIteration, TypeError) as exc:
        raise TranslationError(f"invalid JSON response: {exc}") from exc

    result: dict[str, str] = {}
    for unit in units:
        if unit["id"] in result:
            raise TranslationError(f"duplicate id {unit['id']}")
        result[unit["id"]] = unit["text"]
    missing = [i for i in expected_ids if i not in result]
    extra = [i for i in result if i not in expected_ids]
    empty = [i for i, text in result.items() if not text.strip()]
    if missing:
        raise TranslationError(f"missing ids {missing}")
    if extra:
        raise TranslationError(f"unexpected ids {extra}")
    if empty:
        raise TranslationError(f"empty text for {empty}")
    return result
