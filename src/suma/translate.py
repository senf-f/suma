import json
import time
from dataclasses import dataclass, field
from pathlib import Path

from suma.glossary import load_glossary
from suma.ids import parse_range
from suma.llm import MODELS, message_cost, usage_cost
from suma.prompt import PROMPT_VERSION, TranslationError, build_requests, request_unit_ids, request_units, validate
from suma.store import done_ids, write_units

# Croatian output runs about as long as the Latin, plus adaptive-thinking overhead.
OUTPUT_FACTOR = 2.0
CHARS_PER_TOKEN = 3.5


@dataclass
class Summary:
    written: int = 0
    failed: list[tuple[str, str]] = field(default_factory=list)
    usd_actual: float = 0.0


def estimate_cost(requests: list[dict], client, model: str) -> tuple[int, int, float]:
    input_tokens = 0
    latin_chars = 0
    for request in requests:
        params = request["params"]
        input_tokens += client.messages.count_tokens(
            model=model, system=params["system"], messages=params["messages"]
        ).input_tokens
        latin_chars += sum(len(u["text"]) for u in request_units(request))
    output_tokens = int(OUTPUT_FACTOR * latin_chars / CHARS_PER_TOKEN)
    return input_tokens, output_tokens, usage_cost(model, input_tokens, output_tokens, batch=True)


def _latin_files(data_dir: Path, range_spec: str) -> list[Path]:
    part, q_from, q_to = parse_range(range_spec)
    candidates = [data_dir / "latin" / part / f"q{q:03}.json" for q in range(q_from, q_to + 1)]
    files = [f for f in candidates if f.exists()]
    if not files:
        raise FileNotFoundError(f"No parsed Latin for {range_spec}; run `suma parse --range {range_spec}` first")
    return files


def run_translate(
    range_spec: str,
    model_key: str,
    client,
    yes: bool,
    input_fn=input,
    poll_seconds: int = 60,
    sleep=time.sleep,
    data_dir: Path = Path("data"),
) -> Summary:
    model = MODELS[model_key]
    for path in sorted((data_dir / "batches").glob("*.json")):
        pending = json.loads(path.read_text(encoding="utf-8"))
        if pending["model"] == model and not pending.get("collected"):
            raise RuntimeError(
                f"Batch {path.stem} for {model} was submitted but never collected; "
                f"run `suma translate --collect {path.stem}` instead of submitting again"
            )
    glossary_version, terms = load_glossary(data_dir / "glossary.yaml")
    done = done_ids(model, PROMPT_VERSION, glossary_version, data_dir / "hr")
    requests = build_requests(_latin_files(data_dir, range_spec), model, (glossary_version, terms), done)
    if not requests:
        print("Nothing to translate: every unit in range is already done.")
        return Summary()

    input_tokens, output_tokens, usd = estimate_cost(requests, client, model)
    print(f"{len(requests)} requests to {model}")
    print(f"estimate: {input_tokens:,} input + ~{output_tokens:,} output tokens ≈ ${usd:.2f} (batch rate)")
    if not yes and input_fn("Submit? [y/N] ").strip().lower() != "y":
        print("Aborted.")
        return Summary()

    batch = client.messages.batches.create(requests=requests)
    batches_dir = data_dir / "batches"
    batches_dir.mkdir(parents=True, exist_ok=True)
    record = {
        "model": model,
        "range": range_spec,
        "prompt_version": PROMPT_VERSION,
        "glossary_version": glossary_version,
        "expected": {r["custom_id"]: request_unit_ids(r) for r in requests},
    }
    (batches_dir / f"{batch.id}.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"submitted {batch.id}")
    return collect(batch.id, client, poll_seconds=poll_seconds, sleep=sleep, data_dir=data_dir)


def collect(
    batch_id: str, client, poll_seconds: int = 60, sleep=time.sleep, data_dir: Path = Path("data")
) -> Summary:
    record_path = data_dir / "batches" / f"{batch_id}.json"
    record = json.loads(record_path.read_text(encoding="utf-8"))
    model = record["model"]

    while client.messages.batches.retrieve(batch_id).processing_status != "ended":
        print(f"{batch_id}: processing…")
        sleep(poll_seconds)

    summary = Summary()
    for entry in client.messages.batches.results(batch_id):
        result = entry.result
        if result.type != "succeeded":
            summary.failed.append((entry.custom_id, result.type))
            continue
        summary.usd_actual += message_cost(model, result.message.usage, batch=True)
        expected = record["expected"][entry.custom_id]
        try:
            units = validate(expected, result.message)
        except TranslationError as exc:
            summary.failed.append((entry.custom_id, str(exc)))
            continue
        part, question = expected[0].split(".")[:2]
        write_units(
            model, part, int(question[1:]), units,
            record["prompt_version"], record["glossary_version"], data_dir / "hr",
        )
        summary.written += len(units)

    record["collected"] = True
    record_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary
