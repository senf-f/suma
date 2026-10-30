import json
import re
from pathlib import Path

from selectolax.lexbor import LexborHTMLParser as HTMLParser

from suma.ids import label_to_id

_WS = re.compile(r"\s+")
CT_BASE = "https://www.corpusthomisticum.org"


def _kind(unit_id: str) -> str:
    last = unit_id.rsplit(".", 1)[1]
    for kind in ("obj", "sc", "ad"):
        if last.startswith(kind):
            return kind
    return last


def parse_page(html_bytes: bytes, page: str) -> list[dict]:
    tree = HTMLParser(html_bytes.decode("iso-8859-1"))
    units = []
    for p in tree.css("p[title]"):
        label = p.attributes["title"]
        unit_id = label_to_id(label)
        anchor = p.css_first("a[name]")
        if anchor is None:
            raise ValueError(f"No passage anchor for {label!r}")
        source = f"{CT_BASE}/{page}#{anchor.attributes['name']}"
        for ref in p.css("span.ref"):
            ref.decompose()
        for italic in p.css("i"):
            italic.replace_with(f"*{italic.text()}*")
        text = _WS.sub(" ", p.text()).strip()
        units.append({"id": unit_id, "kind": _kind(unit_id), "text": text, "source": source})
    return units


def write_latin(units: list[dict], part: str, q_from: int, q_to: int, out_dir: Path) -> list[Path]:
    by_question: dict[int, list[dict]] = {}
    for unit in units:
        unit_part, q = unit["id"].split(".")[:2]
        question = int(q[1:])
        if unit_part == part and q_from <= question <= q_to:
            by_question.setdefault(question, []).append(unit)

    written = []
    for question, q_units in sorted(by_question.items()):
        path = out_dir / part / f"q{question:03}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {"id": f"{part}.q{question}", "part": part, "question": question, "units": q_units}
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        written.append(path)
    return written
