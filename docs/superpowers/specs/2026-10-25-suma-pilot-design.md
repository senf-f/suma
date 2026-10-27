# Suma — pilot design (pipeline + minimal reader)

Date: 2026-10-25 · Source idea: senf-f/ideje#13

## Goal

A readable Croatian translation of Aquinas' *Summa Theologiae*, AI-generated from the
Latin and presented as a parallel-text edition that readers can help improve.

- **Audience:** general Croatian readers (students, clergy, laypeople) — readability first.
- **Edition qualities:** Latin/Croatian side by side, a fixed approved glossary, stable citable unit IDs.

This spec covers only the **pilot**: Prima Pars q.1–13, translated by two models, with a
minimal reader to judge quality before paying for the full run (~$60–80 Opus 5.5 batch).

## Decisions

| Topic | Decision |
|---|---|
| Source | Corpus Thomisticum (Leonine text), pages `sth1001.html`… |
| Pilot slice | Prima Pars q.1–13 |
| Stack | Python only (uv); static site via Jinja2; Pagefind search; GitHub Pages |
| API | Anthropic API directly (not Bedrock); Message Batches + prompt caching |
| Models | `claude-opus-5-5` and `claude-sonnet-5-5`, both on the full slice |
| Glossary | Model drafts proposals, owner edits and approves `glossary.yaml` before translation |
| Bible quotations | Translated from the Vulgate Latin as quoted; citation reference kept |
| Suggestions | Per-unit link to a pre-filled GitHub issue; no backend, no auth |

## Repository layout

```
pipeline/                 Python package, CLI entry points per stage
data/
  cache/                  raw Corpus Thomisticum HTML (gitignored)
  latin/I/q001.json …     parsed source (gitignored, see Rights)
  glossary.draft.yaml     model proposals
  glossary.yaml           approved glossary
  hr/<model>/I/q001.json  translations, one directory per model
site/
  build.py, templates/, static/
dist/                     build output (gitignored)
tests/
```

## Text units and IDs

Each translatable unit has a stable ID used in data files, URLs, anchors and issues:

- `I.q2.pr` question prologue (list of articles). Corpus Thomisticum has no separate
  question or article titles; the reader shows "Pitanje 2" / "Članak 3".
- `I.q2.a3.obj1` … objections, `I.q2.a3.sc` sed contra, `I.q2.a3.resp` respondeo,
  `I.q2.a3.ad1` … replies

Latin file shape (`data/latin/I/q002.json`):

```json
{"id": "I.q2", "part": "I", "question": 2,
 "units": [{"id": "I.q2", "kind": "title", "text": "..."},
           {"id": "I.q2.a3.obj1", "kind": "obj", "text": "..."}]}
```

Translation files mirror this, keyed by unit ID, with per-unit metadata
(`prompt_version`, `glossary_version`, `created_at`) and the `model` at file level.

**Rights:** the Corpus Thomisticum footer reserves rights on its digital edition. Until
permission is obtained or another public-domain source is used, `data/cache/` and
`data/latin/` are gitignored and nothing is deployed publicly.

## Pipeline stages

Each stage is a separate CLI command, idempotent and re-runnable.

1. **fetch** — download the needed Corpus Thomisticum pages into `data/cache/`, once,
   sequentially with a delay between requests.
2. **parse** — HTML → Latin JSON. Raises on unrecognised structure rather than guessing.
3. **glossary** — extract recurring technical terms from the slice, ask the model for
   Croatian equivalents (with alternatives and a one-line rationale), write
   `glossary.draft.yaml`. The owner edits it and saves it as `glossary.yaml`, which has a
   `version` field.
4. **translate `--model <id> --range I.q1-13`** — one request per article. The fixed
   system prompt (style guide + glossary) is cached; the article's units go in the user
   message. The model returns structured JSON keyed by unit ID. Requests go through the
   Batch API. Before submitting, the command counts tokens, prints the estimated cost and
   asks for confirmation. Units already translated under the same model, prompt version and
   glossary version are skipped.

### Response validation

A result is accepted only if every requested unit ID is present, non-empty, and no extra IDs
appear. Failed, errored or refused requests are logged and retried individually. A unit
that failed is never written as translated.

## Reader site (pilot)

`site/build.py` renders one page per question from `data/latin` and `data/hr/*`.

- Parallel layout: Croatian left, Latin right, aligned per unit. A toggle hides the Latin.
  On narrow screens the Latin stacks below and can be revealed per unit.
- Model switch (Opus / Sonnet), remembered in localStorage.
- Navigation: table of contents → question → article; previous/next links.
- Every unit has an anchor (`#I.q2.a3.ad1`) and a "copy citation" button.
- Glossary page listing approved terms.
- Pagefind index over the built HTML, both languages.
- "Predloži poboljšanje" link per unit opening a pre-filled GitHub issue
  (`/issues/new?title=…&body=…`) containing the unit ID, Latin, current Croatian, model,
  and an empty suggestion field.
- Interface text in Croatian.

## Testing

- **Parser:** fixed cached pages → expected unit IDs and text for known articles
  (e.g. I q.2 a.3).
- **Translate:** fake API client; covers response validation, skip-if-done, retry of failed
  units, cost estimation. No real API calls in tests.
- **Site:** build over a small fixture; pages render, anchors exist, issue URLs are
  correctly encoded.

## Out of scope (spec 2)

Full Summa run, Supplementum, final visual design, moderation workflow,
CI/CD deployment, choice of final model.
