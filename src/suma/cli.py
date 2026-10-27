import argparse


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="suma", description="Summa Theologiae translation pipeline")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("fetch", help="download Corpus Thomisticum pages into data/cache")
    sub.add_parser("parse", help="parse cached pages into data/latin")
    sub.add_parser("glossary", help="draft a glossary from the parsed slice")
    sub.add_parser("translate", help="translate a range via the Batch API")
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    raise SystemExit(f"'{args.command}' is not implemented yet")
