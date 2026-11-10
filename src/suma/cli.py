import argparse
import os
import sys
from pathlib import Path

from suma.llm import MODELS

DATA = Path("data")


def cmd_fetch(args) -> None:
    from suma.fetch import PILOT_PAGES, fetch_pages, fetch_part, make_client

    with make_client() as client:
        if args.part:
            paths = fetch_part(args.part, DATA / "cache", client)
        else:
            paths = fetch_pages(PILOT_PAGES, DATA / "cache", client)
    print(f"{len(paths)} pages in {DATA / 'cache'}")


def cmd_parse(args) -> None:
    from suma.fetch import PARTS
    from suma.ids import parse_range
    from suma.parse import parse_page, write_latin

    part, q_from, q_to = parse_range(args.range)
    pages = sorted((DATA / "cache").glob(f"{PARTS[part][1]}*.html"))
    if not pages:
        raise SystemExit(f"No cached pages for part {part}; run `suma fetch --part {part}` first")
    units = []
    for page in pages:
        units.extend(parse_page(page.read_bytes(), page.name))
    written = write_latin(units, part, q_from, q_to, DATA / "latin")
    print(f"{len(written)} questions written to {DATA / 'latin'}")


def cmd_glossary(args) -> None:
    import anthropic

    from suma.glossary import draft_glossary, write_draft
    from suma.llm import MODELS, usage_cost

    model = MODELS[args.model]
    result = draft_glossary(DATA / "latin", anthropic.Anthropic(), model)
    usage = result["usage"]
    write_draft(result, DATA / "glossary.draft.yaml")
    cost = usage_cost(model, usage.input_tokens, usage.output_tokens)
    print(f"{len(result['terms'])} terms -> {DATA / 'glossary.draft.yaml'}")
    print(f"tokens in/out: {usage.input_tokens}/{usage.output_tokens}, cost ${cost:.2f}")
    print("Review it, then save as data/glossary.yaml to approve.")


def cmd_translate(args) -> None:
    import anthropic

    from suma.translate import collect, run_translate

    client = anthropic.Anthropic()
    if args.collect:
        summary = collect(args.collect, client, data_dir=DATA)
    else:
        summary = run_translate(args.range, args.model, client, yes=args.yes, data_dir=DATA)
    print(f"written: {summary.written} units, actual cost ${summary.usd_actual:.2f}")
    for custom_id, reason in summary.failed:
        print(f"FAILED {custom_id}: {reason}")
    if summary.failed:
        raise SystemExit("Some articles failed; run the same command again to retry only those.")


def cmd_build(args) -> None:
    import subprocess
    import sys

    from suma.reader import DEFAULT_SITE_URL, build

    out = Path(args.out)
    args.site_url = args.site_url or os.environ.get("SUMA_SITE_URL") or DEFAULT_SITE_URL
    build(DATA / "latin", Path(args.hr), DATA / "glossary.yaml", out, site_url=args.site_url, with_latin=args.with_latin)
    subprocess.run([sys.executable, "-m", "pagefind", "--site", str(out)], check=True)
    print(f"Site built in {out}; open {out / 'index.html'}")
    if args.with_latin:
        print("Contains Corpus Thomisticum Latin: local review only, do not deploy or share.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="suma", description="Summa Theologiae translation pipeline")
    sub = parser.add_subparsers(dest="command", required=True)
    p_fetch = sub.add_parser("fetch", help="download Corpus Thomisticum pages into data/cache")
    p_fetch.add_argument("--part", help="follow the page chain of a whole Part (e.g. I) instead of the pilot pages")
    p_fetch.set_defaults(func=cmd_fetch)
    p_parse = sub.add_parser("parse", help="parse cached pages into data/latin")
    p_parse.add_argument("--range", default="I.q1-13")
    p_parse.set_defaults(func=cmd_parse)
    p_gloss = sub.add_parser("glossary", help="draft a glossary from the parsed slice")
    p_gloss.add_argument("--model", choices=sorted(MODELS), default="opus")
    p_gloss.set_defaults(func=cmd_glossary)
    p_tr = sub.add_parser("translate", help="translate a range via the Batch API")
    p_tr.add_argument("--model", choices=sorted(MODELS), default="opus")
    p_tr.add_argument("--range", default="I.q1-13")
    p_tr.add_argument("--yes", action="store_true", help="submit without asking for confirmation")
    p_tr.add_argument("--collect", metavar="BATCH_ID", help="collect results of an already submitted batch")
    p_tr.set_defaults(func=cmd_translate)
    p_build = sub.add_parser("build", help="render the reader site into dist/ and index it")
    p_build.add_argument("--out", default="dist")
    p_build.add_argument("--hr", default=str(DATA / "hr"), help="translations directory")
    p_build.add_argument(
        "--with-latin", action="store_true", help="add the parallel Latin column (local review only, never deploy)"
    )
    p_build.add_argument("--site-url", help="public URL cited in suggestion issues (default: $SUMA_SITE_URL, else suma.oprobate.eu)")
    p_build.set_defaults(func=cmd_build)
    return parser


def main(argv: list[str] | None = None) -> None:
    # Windows consoles and pipes default to cp1250, which can't print Croatian or "≈".
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = build_parser().parse_args(argv)
    if not hasattr(args, "func"):
        raise SystemExit(f"'{args.command}' is not implemented yet")
    args.func(args)
