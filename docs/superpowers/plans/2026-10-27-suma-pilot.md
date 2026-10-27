# Suma Pilot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fetch and parse Prima Pars q.1–13 from Corpus Thomisticum, draft a glossary, translate the slice into Croatian with two models via the Batch API, and render a local parallel-text reader.

**Architecture:** A Python package `suma` with one module per pipeline stage (fetch, parse, glossary, translate) behind a single `suma` CLI. Data moves between stages as JSON/YAML files under `data/`. `site/build.py` renders static HTML from those files into `dist/`, and Pagefind indexes it.

**Tech Stack:** Python ≥3.12 via `uv`; `httpx`, `selectolax`, `anthropic`, `pyyaml`, `jinja2`, `pagefind[extended]`; `pytest`.

**Spec:** `docs/superpowers/specs/2026-10-25-suma-pilot-design.md`

## Global Constraints

- Every file read/write passes `encoding="utf-8"`; JSON is written with `ensure_ascii=False, indent=2`. (Windows defaults to cp1250 and would corrupt č ć đ š ž.)
- Source pages are ISO-8859-1; decode them as such.
- **Rights:** Corpus Thomisticum claims rights on its digital edition ("Iura omnia asservantur"). `data/cache/` and `data/latin/` are gitignored, and nothing is deployed publicly in this pilot.
- Fetching: sequential, ≥2 s between requests, User-Agent `suma-pilot (personal research; contact via github.com/senf-f)`, never refetch a cached page.
- Models: exactly `claude-opus-5-5` and `claude-sonnet-5-5`. Prices per MTok (input/output): Opus 4/20, Sonnet 2/10; Batch API halves both.
- Anthropic API directly (`anthropic.Anthropic()`, credentials from env/`ant` profile). Never Bedrock.
- Pilot range: `I.q1-13`.
- Unit IDs: `I.q2.pr`, `I.q2.a3.obj1`, `I.q2.a3.sc`, `I.q2.a3.resp`, `I.q2.a3.ad1`.
- Batch `custom_id` must match `^[a-zA-Z0-9_-]{1,64}$`: use the article ID with dots replaced by `-` (`I-q2-a3`, `I-q2-pr`).
- Italic spans in the Latin (`<I>…</I>`, quotations) are stored as `*…*` and must survive translation and rendering.
- Tests never call the network or the real API.
- Site UI text is Croatian. All site links are relative (the site will later live under a sub-path).
- `PROMPT_VERSION = "1"`, bumped whenever the translation prompt changes.

## Review Focus

1. **Range boundary:** `sth1003.html` holds q.3–14. A run for `I.q1-13` must contain no q.14 units. Tested in Task 3.
2. **Entities and italics:** `&ordf;`, `&aelig;`, `&oelig;` and `<I>` must become proper Unicode and `*…*`, with no stray tags or entity text. Tested in Task 3.
3. **Bad model output:** missing IDs, extra IDs, empty text, invalid JSON, `stop_reason: "refusal"`, or an errored/expired batch result must not be written as translated. Tested in Task 5.
4. **Long units in issue links:** a long `resp` (e.g. I q.2 a.3) can push a pre-filled issue URL past GitHub's ~8 KB limit. Truncate Latin and Croatian in the body to 1500 chars each with `…` plus a link to the unit. Tested in Task 7.
5. **Sub-path hosting:** opening `dist/I/q002.html` from disk or under `/suma/` must not break CSS, JS or navigation. Every href is relative. Tested in Task 7.

---

### Task 1: Project scaffold and unit IDs

**Files:**
- Create: `pyproject.toml`, `.gitignore`, `src/suma/__init__.py`, `src/suma/ids.py`, `src/suma/cli.py`, `tests/test_ids.py`

**Interfaces:**
- Produces:
  - `label_to_id(label: str) -> str`, e.g. `"I q. 2 a. 1 arg. 1"` → `"I.q2.a1.obj1"`; `"I q. 2 pr."` → `"I.q2.pr"`; `"s. c."` → `sc`; `"co."` → `resp`; `"ad 3"` → `ad3`. Raises `ValueError` on anything else.
  - `article_of(unit_id: str) -> str`: `"I.q2.a3.ad1"` → `"I.q2.a3"`; `"I.q2.pr"` → `"I.q2.pr"`.
  - `parse_range(spec: str) -> tuple[str, int, int]`: `"I.q1-13"` → `("I", 1, 13)`; `"I.q5"` → `("I", 5, 5)`.
  - `custom_id(article_id: str) -> str`: dots → `-`.
  - CLI entry point `suma = "suma.cli:main"` with argparse subcommands `fetch`, `parse`, `glossary`, `translate`, filled in by later tasks.

- [ ] **Step 1:** `uv init --package --name suma`, then add the deps from Tech Stack and `pytest` as a dev dep. `.gitignore`: `data/cache/`, `data/latin/`, `dist/`, `.venv/`, `__pycache__/`.
- [ ] **Step 2: Write failing tests** in `tests/test_ids.py`, covering every example in Interfaces plus `label_to_id("I q. 2 a. 1 foo")` raising `ValueError`.
- [ ] **Step 3:** Run `uv run pytest tests/test_ids.py -v`. Expected: FAIL (import error).
- [ ] **Step 4:** Implement `ids.py` with one regex over the label: `^(I|I-II|II-II|III) q\. (\d+) (?:pr\.|a\. (\d+) (arg\. (\d+)|s\. c\.|co\.|ad (\d+)))$`. Add the CLI skeleton.
- [ ] **Step 5:** Run `uv run pytest -v` and `uv run suma --help`. Expected: PASS, help lists 4 subcommands.
- [ ] **Step 6:** Commit `feat: scaffold project and unit ID helpers`.

### Task 2: Fetch

**Files:**
- Create: `src/suma/fetch.py`, `tests/test_fetch.py`

**Interfaces:**
- Produces:
  - `PILOT_PAGES = ["sth1001.html", "sth1002.html", "sth1003.html"]`
  - `fetch_pages(pages: list[str], cache_dir: Path, client: httpx.Client, delay: float = 2.0, sleep=time.sleep) -> list[Path]`: downloads `https://www.corpusthomisticum.org/<page>` into `cache_dir/<page>` as raw bytes, skips files already cached, and calls `sleep(delay)` between actual downloads only.
  - CLI: `suma fetch` → `fetch_pages(PILOT_PAGES, Path("data/cache"), ...)`.

- [ ] **Step 1: Write failing tests** using `httpx.MockTransport`:
  - `test_fetch_downloads_and_caches`: 3 pages → 3 files whose bytes match the mock, `sleep` called 2 times.
  - `test_fetch_skips_cached`: pre-create one file → only 2 requests made.
  - `test_fetch_raises_on_http_error`: a 404 raises `httpx.HTTPStatusError` and leaves no partial file.
- [ ] **Step 2:** Run `uv run pytest tests/test_fetch.py -v`. Expected: FAIL.
- [ ] **Step 3:** Implement. Write to a `.part` file, then rename.
- [ ] **Step 4:** Run tests. Expected: PASS. Then run `uv run suma fetch` for real once. Expected: 3 files in `data/cache/`.
- [ ] **Step 5:** Commit `feat: fetch and cache Corpus Thomisticum pages`.

### Task 3: Parse

**Files:**
- Create: `src/suma/parse.py`, `tests/test_parse.py`, `tests/fixtures/sth_sample.html`

**Interfaces:**
- Consumes: `label_to_id`, `parse_range` (Task 1).
- Produces:
  - `parse_page(html_bytes: bytes) -> list[dict]`: `[{"id": "I.q2.a1.obj1", "kind": "obj", "text": "..."}]` in document order. `kind` ∈ `pr, obj, sc, resp, ad`.
  - `write_latin(units: list[dict], part: str, q_from: int, q_to: int, out_dir: Path) -> list[Path]`: groups by question, keeps only `q_from..q_to`, writes `out_dir/<part>/q{n:03}.json` as `{"id": "I.q2", "part": "I", "question": 2, "units": [...]}`.
  - CLI: `suma parse --range I.q1-13` parses every cached pilot page and writes `data/latin/`.

- [ ] **Step 1: Build the fixture**: a hand-trimmed ISO-8859-1 HTML file containing, from the real pages: `I q. 2 pr.`, all units of `I q. 2 a. 3` (whose `s. c.` contains `<I>ego sum qui sum</I>`), one unit labelled `I q. 14 a. 1 arg. 1`, the `&ordf;` ref spans, one `&aelig;` word, and the two untitled navigation `<P>` elements.
- [ ] **Step 2: Write failing tests:**
  - `test_parse_ids_in_order`: IDs equal `["I.q2.pr", "I.q2.a3.obj1", "I.q2.a3.obj2", "I.q2.a3.sc", "I.q2.a3.resp", "I.q2.a3.ad1", "I.q2.a3.ad2", "I.q14.a1.obj1"]`.
  - `test_ref_span_removed`: no text contains `[28` or `Iª q.`.
  - `test_italics_and_entities`: the `sc` text ends with `*ego sum qui sum*.` and the `æ` word is decoded.
  - `test_write_latin_respects_range` (Review Focus 1): range 1–13 writes `I/q002.json` only, with no `q014.json`.
  - `test_unknown_label_raises`: a `<P TITLE="I q. 2 a. 3 xyz">` raises `ValueError`.
- [ ] **Step 3:** Run `uv run pytest tests/test_parse.py -v`. Expected: FAIL.
- [ ] **Step 4:** Implement with `selectolax`: iterate `p[title]`, drop `span.ref`, convert `<i>` to `*…*`, collapse whitespace, strip.
- [ ] **Step 5:** Run tests. Expected: PASS. Run `uv run suma parse --range I.q1-13`. Expected: 13 files. Spot-check that `I/q002.json` has 23 units.
- [ ] **Step 6:** Commit `feat: parse Corpus Thomisticum pages into unit JSON`.

### Task 4: Glossary draft

**Files:**
- Create: `src/suma/llm.py`, `src/suma/glossary.py`, `tests/test_glossary.py`

**Interfaces:**
- Produces:
  - `llm.MODELS = {"opus": "claude-opus-5-5", "sonnet": "claude-sonnet-5-5"}`, `llm.PRICES = {"claude-opus-5-5": (4.0, 20.0), "claude-sonnet-5-5": (2.0, 10.0)}` (USD per MTok in/out, before the batch discount).
  - `glossary.GLOSSARY_SCHEMA`: JSON schema `{"terms": [{"la": str, "hr": str, "alternatives": [str], "note": str}]}` with `additionalProperties: false`.
  - `draft_glossary(latin_dir: Path, client, model: str) -> dict`: one streaming `messages` request with all slice units (IDs + text) in the user message, `output_config={"format": {"type": "json_schema", "schema": GLOSSARY_SCHEMA}}` and `effort: "high"`. Asks for the ~100 recurring philosophical/theological terms with standard Croatian equivalents, alternatives and a one-line rationale. Raises on `stop_reason` other than `end_turn`.
  - `write_draft(terms: dict, path: Path)` writes YAML `{"version": 1, "terms": [...]}`.
  - `load_glossary(path: Path) -> tuple[int, list[dict]]`: raises `FileNotFoundError` with the message `Glossary not approved: copy data/glossary.draft.yaml to data/glossary.yaml after review` when the file is missing.
  - CLI: `suma glossary [--model opus]` writes `data/glossary.draft.yaml` and prints the token usage and cost.

- [ ] **Step 1: Write failing tests** with a fake client whose `messages.stream(...)` context returns a canned final message:
  - `test_draft_parses_terms`: canned JSON → dict with 2 terms; the request used `claude-opus-5-5` and the schema.
  - `test_draft_raises_on_refusal`: `stop_reason="refusal"` raises.
  - `test_yaml_roundtrip_utf8`: `write_draft` then `load_glossary` preserves `"bitak"`, `"čin"`, `"zbiljnost"`, and the version is 1.
  - `test_missing_glossary_message`.
- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run. Expected: PASS.
- [ ] **Step 5:** Commit `feat: draft glossary from slice via Claude`.

### Task 5: Translation requests, validation and storage

**Files:**
- Create: `src/suma/prompt.py`, `src/suma/store.py`, `tests/test_prompt.py`, `tests/test_store.py`

**Interfaces:**
- Consumes: `article_of`, `custom_id` (Task 1); `load_glossary` (Task 4).
- Produces:
  - `prompt.PROMPT_VERSION = "1"`.
  - `prompt.system_prompt(glossary_terms: list[dict]) -> str`. It states:
    - Translate into standard Croatian (ijekavian, current orthography) for educated general readers.
    - Faithful but readable: split very long Latin periods where needed.
    - Use fixed formulas consistently: `Ad primum sic proceditur` → "Čini se da…" opening; `Sed contra` → "Ali protiv toga"; `Respondeo dicendum quod` → "Odgovaram: treba reći da"; `Ad primum ergo dicendum` → "Na prvo, dakle, treba reći".
    - Always use the glossary's `hr` term.
    - Translate Scripture quotations from the Latin as quoted, and keep references.
    - Preserve `*…*` spans.
    - Return every unit ID exactly once.
  - `prompt.TRANSLATION_SCHEMA`: `{"units": [{"id": str, "text": str}]}`, `additionalProperties: false`.
  - `prompt.build_requests(latin_files: list[Path], model: str, glossary: tuple[int, list[dict]], done: set[str]) -> list[dict]`: one Batch request per article. The unit IDs not in `done` are grouped by `article_of`. Shape: `{"custom_id": ..., "params": {"model", "max_tokens": 32000, "system": [{"type": "text", "text": ..., "cache_control": {"type": "ephemeral"}}], "messages": [user msg with question ID + units as JSON], "output_config": {"format": ..., "effort": "medium"}}}`.
  - `prompt.validate(expected_ids: list[str], message) -> dict[str, str]`: returns `{id: text}` or raises `TranslationError(reason)` for each of these: `stop_reason != "end_turn"`, unparseable JSON, missing ID, extra ID, empty/whitespace text.
  - `store.done_ids(model: str, prompt_version: str, glossary_version: int, hr_dir: Path) -> set[str]`.
  - `store.write_units(model: str, part: str, question: int, units: dict[str, str], prompt_version: str, glossary_version: int, hr_dir: Path)`: merges into `hr_dir/<model>/<part>/q{n:03}.json` (`{"model", "question", "units": {id: {"text", "prompt_version", "glossary_version", "created_at"}}}`), preserving existing units.

- [ ] **Step 1: Write failing tests:**
  - `test_build_requests_groups_by_article`: `I/q002.json` fixture → custom_ids `I-q2-pr, I-q2-a1, I-q2-a2, I-q2-a3`; each custom_id matches the regex; the system block has `cache_control`.
  - `test_build_requests_skips_done`: every unit of `I.q2.a1` in `done` → no `I-q2-a1` request.
  - `test_system_prompt_contains_glossary`: contains `"esse → bitak"` for a glossary term.
  - `test_validate_ok`; `test_validate_missing_id`; `test_validate_extra_id`; `test_validate_empty_text`; `test_validate_bad_json`; `test_validate_refusal` (Review Focus 3). Each failure test asserts `TranslationError`.
  - `test_store_merge_and_done`: write `a1` units, then `a2` units → the file has both; `done_ids` with glossary version 1 returns them, and with version 2 returns an empty set.
- [ ] **Step 2:** Run `uv run pytest tests/test_prompt.py tests/test_store.py -v`. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run. Expected: PASS.
- [ ] **Step 5:** Commit `feat: build translation requests, validate and store results`.

### Task 6: Translate command (cost guard + Batch API)

**Files:**
- Create: `src/suma/translate.py`, `tests/test_translate.py`

**Interfaces:**
- Consumes: everything in Task 5; `llm.MODELS`, `llm.PRICES`.
- Produces:
  - `estimate_cost(requests: list[dict], client, model: str) -> tuple[int, int, float]`: input tokens via `client.messages.count_tokens` per request (summed); estimated output = `2.0 ×` the Latin unit characters `/ 3.5` (Croatian output plus reasoning). Returns `(input_tokens, est_output_tokens, usd)` with the batch 50% discount applied.
  - `run_translate(range_spec: str, model_key: str, client, yes: bool, input_fn=input, poll_seconds: int = 60, sleep=time.sleep) -> Summary`:
    1. Build the requests.
    2. Print the count and estimate.
    3. Unless `yes`, `input_fn("Submit? [y/N] ")` must return `y`.
    4. `client.messages.batches.create(requests=...)`, and save `data/batches/<batch_id>.json` (model, range, custom_id → expected IDs).
    5. Poll `batches.retrieve` until `processing_status == "ended"`.
    6. Iterate `batches.results`: write `succeeded` results that pass `validate`, and collect failures `(custom_id, reason)` for `errored`, `expired`, `canceled` or a `TranslationError`.
    7. Return `Summary(written: int, failed: list[tuple[str, str]], usd_actual: float)`, where `usd_actual` comes from the summed `usage`.
  - `collect(batch_id: str, client) -> Summary` does steps 5–7 from the saved file (for interrupted runs).
  - CLI: `suma translate --model {opus,sonnet} --range I.q1-13 [--yes]` and `suma translate --collect <batch_id>`. Prints the summary and exits non-zero when there are failures. Re-running `translate` retries only the missing units.

- [ ] **Step 1: Write failing tests** with a fake client (count_tokens, batches.create/retrieve/results):
  - `test_aborts_without_confirmation`: `input_fn` returns `"n"` → `batches.create` is never called.
  - `test_happy_path_writes_units`: 2 requests, both succeed → both written, `failed == []`.
  - `test_mixed_results`: one `errored`, one succeeded with a missing ID → `written == 0` for those units and 2 failures with reasons; the store file has neither.
  - `test_rerun_only_missing`: after the mixed run, `build_requests` yields exactly the 2 failed custom_ids.
  - `test_estimate_applies_batch_discount`: 1M input tokens at Opus with output forced to 0 → `usd == 2.0`.
- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run `uv run pytest -v`. Expected: all PASS.
- [ ] **Step 5:** Commit `feat: translate command with cost guard and batch processing`.

### Task 7: Reader site

**Files:**
- Create: `site/build.py`, `site/templates/base.html`, `site/templates/index.html`, `site/templates/question.html`, `site/templates/glossary.html`, `site/static/style.css`, `site/static/reader.js`, `tests/test_site.py`

**Interfaces:**
- Consumes: the `data/latin`, `data/hr/<model>` and `data/glossary.yaml` formats.
- Produces:
  - `build(latin_dir: Path, hr_dir: Path, glossary_path: Path, out_dir: Path, repo: str = "senf-f/suma") -> None` writes:
    - `index.html`: table of contents; questions grouped by part, with article links.
    - `I/q002.html`: one row per unit with `id="I.q2.a3.ad1"`. The left cell holds one `<div data-model="claude-opus-5-5">` per model (Croatian, with `*…*` rendered as `<em>`). The right cell holds the Latin. Units get Croatian labels: `Uvod`, `Prigovor 1`, `Ali protiv toga`, `Odgovor`, `Odgovor na 1`. Articles get `Članak 3` headings, and the page has prev/next links.
    - `glosar.html`, plus `static/` copied.
  - `issue_url(repo: str, unit_id: str, latin: str, hr: str, model: str, page_url: str) -> str`: `https://github.com/<repo>/issues/new?title=<quoted "[prijedlog] I q.2 a.3 ad 1">&labels=prijedlog&body=<quoted>`. The body has the sections `Jedinica`, `Model`, `Latinski`, `Trenutni prijevod`, `Prijedlog` (empty), `Obrazloženje` (empty), and a link to `page_url#unit_id`. Latin and Croatian are truncated to 1500 chars + `…`.
  - `reader.js` handles:
    - The Latin toggle (body class).
    - The model switch: shows the matching `data-model` divs, remembered in localStorage inside try/catch.
    - The per-unit "Kopiraj citat" button, which copies `Toma Akvinski, Summa theologiae I, q. 2, a. 3, ad 1`.
  - CLI: `uv run python site/build.py` builds into `dist/`, then runs `uv run python -m pagefind --site dist`.

- [ ] **Step 1: Write failing tests** using a fixture with one Latin question and two model translations:
  - `test_question_page_has_anchors_and_models`: `dist/I/q002.html` contains `id="I.q2.a3.ad1"` and both `data-model` values.
  - `test_italics_rendered`: `*ego sum qui sum*` → `<em>ego sum qui sum</em>` (the text itself is HTML-escaped).
  - `test_links_are_relative` (Review Focus 5): no `href="/` or `src="/` anywhere in `dist/`, and the question page references `../static/style.css`.
  - `test_issue_url_truncates` (Review Focus 4): a 5000-char Latin text → `len(url) < 8000`, the decoded body contains `…` and `#I.q2.a3.resp`.
  - `test_issue_url_encoding`: Croatian `č`, `&` and newlines round-trip through `urllib.parse.parse_qs`.
  - `test_missing_translation_shows_placeholder`: a unit with no Croatian for a model renders `Prijevod još nije dostupan.`
- [ ] **Step 2:** Run `uv run pytest tests/test_site.py -v`. Expected: FAIL.
- [ ] **Step 3:** Implement. Jinja2 with autoescape on, and a small `md_em` filter applied after escaping. CSS: two columns ≥ 900px, stacked below, Latin hidden with `body.hide-la`. Readable serif body font.
- [ ] **Step 4:** Run. Expected: PASS. Build from the real `data/` (when translations exist), open `dist/index.html` in a browser, and check: navigation, Latin toggle, model switch, copy citation, search box, and an issue link opening a pre-filled GitHub form.
- [ ] **Step 5:** Commit `feat: static parallel-text reader`.

### Task 8: Pilot run (manual, spends money)

No new code. The owner approves each paid step.

- [ ] **Step 1:** `uv run suma fetch && uv run suma parse --range I.q1-13`.
- [ ] **Step 2:** `uv run suma glossary`. Expected cost < $1. The owner reviews `data/glossary.draft.yaml` and saves it as `data/glossary.yaml`, then commits the glossary.
- [ ] **Step 3:** `uv run suma translate --model opus --range I.q1-13`, then the same with `--model sonnet`. Confirm each estimate before submitting (expected total ~$1–3).
- [ ] **Step 4:** Build the site and run Pagefind. The owner reads both versions and decides the model for the full run (input to spec 2).
- [ ] **Step 5:** Commit `data/hr/` and the glossary (`data/latin` stays ignored).
