import argparse
from pathlib import Path

DATA = Path("data")


def cmd_fetch(args) -> None:
    from suma.fetch import PILOT_PAGES, fetch_pages, make_client

    with make_client() as client:
        paths = fetch_pages(PILOT_PAGES, DATA / "cache", client)
    print(f"{len(paths)} pages in {DATA / 'cache'}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="suma", description="Summa Theologiae translation pipeline")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("fetch", help="download Corpus Thomisticum pages into data/cache").set_defaults(func=cmd_fetch)
    sub.add_parser("parse", help="parse cached pages into data/latin")
    sub.add_parser("glossary", help="draft a glossary from the parsed slice")
    sub.add_parser("translate", help="translate a range via the Batch API")
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    if not hasattr(args, "func"):
        raise SystemExit(f"'{args.command}' is not implemented yet")
    args.func(args)
