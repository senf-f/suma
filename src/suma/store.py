import json
from datetime import UTC, datetime
from pathlib import Path


def _question_path(hr_dir: Path, model: str, part: str, question: int) -> Path:
    return hr_dir / model / part / f"q{question:03}.json"


def done_ids(model: str, prompt_version: str, glossary_version: int, hr_dir: Path) -> set[str]:
    done = set()
    for path in (hr_dir / model).glob("*/q*.json"):
        units = json.loads(path.read_text(encoding="utf-8"))["units"]
        done.update(
            unit_id
            for unit_id, unit in units.items()
            if unit["prompt_version"] == prompt_version and unit["glossary_version"] == glossary_version
        )
    return done


def write_units(
    model: str,
    part: str,
    question: int,
    units: dict[str, str],
    prompt_version: str,
    glossary_version: int,
    hr_dir: Path,
) -> None:
    path = _question_path(hr_dir, model, part, question)
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
    else:
        data = {"model": model, "question": question, "units": {}}
    created_at = datetime.now(UTC).isoformat(timespec="seconds")
    for unit_id, text in units.items():
        data["units"][unit_id] = {
            "text": text,
            "prompt_version": prompt_version,
            "glossary_version": glossary_version,
            "created_at": created_at,
        }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
