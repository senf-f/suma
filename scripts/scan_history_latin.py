"""Scan every blob in git history for Corpus Thomisticum Latin before pushing.

Corpus Thomisticum allows translation and deep links, but its Latin text must never be
published, and a public repo publishes all of history, not just the current tree.
Flags any line (outside the Croatian store data/hr/) dense with Latin function words.
Lines containing "fictus" are skipped: the parser test fixture uses invented Latin.

Usage: uv run python scripts/scan_history_latin.py   (exit 0 = clean, 1 = hits)
"""
import re
import subprocess
import sys

LATIN_WORDS = re.compile(
    r"\b(quod|est|sed|enim|autem|ergo|dicendum|videtur|sicut|igitur|non|esse|unde|quia)\b", re.IGNORECASE
)
MIN_HITS = 6


def suspicious_lines(text: str) -> list[str]:
    return [line for line in text.splitlines() if len(LATIN_WORDS.findall(line)) >= MIN_HITS and "fictus" not in line]


def main() -> int:
    objects = subprocess.run(["git", "rev-list", "--all", "--objects"], capture_output=True, text=True, check=True)
    found: dict[str, list[tuple[str, int]]] = {}
    for line in objects.stdout.splitlines():
        sha, _, path = line.partition(" ")
        if not path or path.startswith("data/hr/"):
            continue
        kind = subprocess.run(["git", "cat-file", "-t", sha], capture_output=True, text=True).stdout.strip()
        if kind != "blob":
            continue
        data = subprocess.run(["git", "cat-file", "blob", sha], capture_output=True).stdout.decode("utf-8", "replace")
        if hits := suspicious_lines(data):
            found.setdefault(path, []).append((sha[:7], len(hits)))
    for path, blobs in found.items():
        print(path, blobs)
    if found:
        return 1
    print("clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
