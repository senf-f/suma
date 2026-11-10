import re
import shutil
from pathlib import Path
from urllib.parse import quote, urlencode

import yaml
from jinja2 import Environment, PackageLoader
from markupsafe import Markup, escape

from suma.llm import load_question

PART_ORDER = ["I", "I-II", "II-II", "III"]
PART_LABELS = {"I": "Prvi dio", "I-II": "Prvi dio Drugoga dijela", "II-II": "Drugi dio Drugoga dijela", "III": "Treći dio"}
MODEL_LABELS = {"claude-opus-5-5": "Opus 5.5", "claude-sonnet-5-5": "Sonnet 5.5", "claude-haiku-5-5": "Haiku 5.5"}
ISSUE_EXCERPT = 1500
_EM = re.compile(r"\*(.+?)\*")

DEFAULT_SITE_URL = "https://suma.oprobate.eu"


def md_em(text: str) -> Markup:
    return Markup(_EM.sub(r"<em>\1</em>", str(escape(text))))


def _split(unit_id: str) -> tuple[str, int, int | None, str]:
    parts = unit_id.split(".")
    part, question = parts[0], int(parts[1][1:])
    if parts[2] == "pr":
        return part, question, None, "pr"
    return part, question, int(parts[2][1:]), parts[3]


def unit_label(last: str) -> str:
    if last == "pr":
        return "Uvod"
    if last == "resp":
        return "Odgovor"
    if last == "adarg":
        return "Odgovor na prigovore"
    if last.startswith("obj"):
        return f"Prigovor {last[3:]}"
    if last.startswith("sc"):
        return f"Ali protiv toga {last[2:]}".strip()
    return f"Odgovor na {last[2:]}"


def _latin_abbrev(last: str) -> str:
    if last == "pr":
        return "pr."
    if last == "resp":
        return "co."
    if last == "adarg":
        return "ad arg."
    if last.startswith("obj"):
        return f"arg. {last[3:]}"
    if last.startswith("sc"):
        return f"s. c. {last[2:]}".strip()
    return f"ad {last[2:]}"


def citation(unit_id: str) -> str:
    part, question, article, last = _split(unit_id)
    location = f"q. {question}" + (f", a. {article}" if article else "")
    return f"Toma Akvinski, Summa theologiae {part}, {location}, {_latin_abbrev(last)}"


def _short_label(unit_id: str) -> str:
    part, question, article, last = _split(unit_id)
    names = {"pr": "uvod", "resp": "odgovor", "adarg": "ad arg."}
    if last in names:
        tail = names[last]
    elif last.startswith("obj"):
        tail = f"prigovor {last[3:]}"
    elif last.startswith("sc"):
        tail = "sed contra"
    else:
        tail = f"ad {last[2:]}"
    return f"{part} q.{question}" + (f" a.{article}" if article else "") + f" {tail}"


def _excerpt(text: str) -> str:
    return text if len(text) <= ISSUE_EXCERPT else text[:ISSUE_EXCERPT].rstrip() + "…"


def issue_url(repo: str, unit_id: str, source: str, hr: str, model: str, page_url: str) -> str:
    # Link to the Latin, never quote it: Corpus Thomisticum does not permit republishing its text.
    body = (
        f"**Jedinica:** {unit_id}\n"
        f"**Model:** {model}\n"
        f"**Poveznica:** {page_url}#{unit_id}\n"
        f"**Latinski izvornik:** {source}\n\n"
        f"### Trenutni prijevod\n{_excerpt(hr)}\n\n"
        "### Prijedlog\n\n\n"
        "### Obrazloženje\n\n"
    )
    query = urlencode(
        {"title": f"[prijedlog] {_short_label(unit_id)}", "labels": "prijedlog", "body": body},
        quote_via=quote,
    )
    return f"https://github.com/{repo}/issues/new?{query}"


def _question_files(latin_dir: Path) -> list[Path]:
    files = latin_dir.glob("*/q*.json")
    return sorted(files, key=lambda p: (PART_ORDER.index(p.parent.name), p.name))


def _load_translations(hr_dir: Path) -> dict[str, dict[str, str]]:
    """model -> unit id -> Croatian text"""
    result: dict[str, dict[str, str]] = {}
    if not hr_dir.exists():
        return result
    for model_dir in sorted(p for p in hr_dir.iterdir() if p.is_dir()):
        texts = result.setdefault(model_dir.name, {})
        for path in model_dir.glob("*/q*.json"):
            for unit_id, unit in load_question(path)["units"].items():
                texts[unit_id] = unit["text"]
    return result


def _sections(question: dict, translations: dict, repo: str, page_url: str) -> list[dict]:
    sections: list[dict] = []
    for unit in question["units"]:
        _, _, article, last = _split(unit["id"])
        key = f"{question['id']}.a{article}" if article else f"{question['id']}.pr"
        if not sections or sections[-1]["key"] != key:
            sections.append({
                "key": key,
                "anchor": key if article else None,
                "heading": f"Članak {article}" if article else "Uvod u pitanje",
                "units": [],
            })
        versions = []
        for model, texts in translations.items():
            text = texts.get(unit["id"])
            versions.append({
                "model": model,
                "text": text,
                "issue": issue_url(repo, unit["id"], unit["source"], text, model, page_url) if text else None,
            })
        if not versions:
            versions.append({"model": "", "text": None, "issue": None})
        sections[-1]["units"].append({
            "id": unit["id"],
            "label": unit_label(last),
            "cite": citation(unit["id"]),
            "source": unit["source"],
            "latin": unit["text"],
            "translations": versions,
        })
    return sections


def _reader_term(term: dict) -> dict | None:
    """Reader view of a glossary term: the translator `note` stays out, `prikaz` overrides the shown Latin, `opis: null` hides meta entries."""
    if "opis" in term and term["opis"] is None:
        return None
    view = {"la": term.get("prikaz", term["la"]), "hr": term["hr"], "alternatives": term.get("alternatives", []), "opis": term.get("opis")}
    if mjesto := term.get("mjesto"):
        part, question, _, _ = _split(mjesto)
        view["href"] = f"{part}/q{question:03}.html#{mjesto}"
        view["cite"] = citation(mjesto).removeprefix("Toma Akvinski, Summa theologiae ")
    return view


def build(
    latin_dir: Path,
    hr_dir: Path,
    glossary_path: Path,
    out_dir: Path,
    repo: str = "senf-f/suma",
    site_url: str = DEFAULT_SITE_URL,
    with_latin: bool = False,
) -> None:
    """Render the reader. with_latin adds the parallel Latin column: local review only, never deploy it."""
    env = Environment(loader=PackageLoader("suma", "reader_templates"), autoescape=True)
    env.filters["md_em"] = md_em
    translations = _load_translations(hr_dir)
    models = [{"id": m, "label": MODEL_LABELS.get(m, m)} for m in translations]

    out_dir.mkdir(parents=True, exist_ok=True)
    shutil.copytree(Path(__file__).parent / "reader_static", out_dir / "static", dirs_exist_ok=True)

    files = _question_files(latin_dir)
    questions = [load_question(p) for p in files]
    toc = []
    for i, question in enumerate(questions):
        rel = f"{question['part']}/q{question['question']:03}.html"
        sections = _sections(question, translations, repo, f"{site_url}/{rel}")
        toc.append({"question": question, "href": rel, "sections": sections})
        neighbours = {
            name: f"../{other['part']}/q{other['question']:03}.html"
            for name, j in (("prev", i - 1), ("next", i + 1))
            if 0 <= j < len(questions)
            for other in [questions[j]]
        }
        html = env.get_template("question.html").render(
            root="../",
            title=f"{question['part']}, pitanje {question['question']}",
            models=models,
            with_latin=with_latin,
            part_label=PART_LABELS[question["part"]],
            q=question,
            sections=sections,
            prev=neighbours.get("prev"),
            next=neighbours.get("next"),
        )
        target = out_dir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(html, encoding="utf-8")

    (out_dir / "index.html").write_text(
        env.get_template("index.html").render(root="", title="Sadržaj", models=[], toc=toc, part_labels=PART_LABELS),
        encoding="utf-8",
    )

    # Served for any missing path, so its links must be absolute.
    (out_dir / "404.html").write_text(
        env.get_template("404.html").render(root="/", title="Stranica nije pronađena", models=[]),
        encoding="utf-8",
    )

    terms = []
    if glossary_path.exists():
        terms = [_reader_term(t) for t in yaml.safe_load(glossary_path.read_text(encoding="utf-8"))["terms"]]
        terms = [t for t in terms if t is not None]
    (out_dir / "glosar.html").write_text(
        env.get_template("glossary.html").render(root="", title="Glosar", models=[], terms=terms),
        encoding="utf-8",
    )
