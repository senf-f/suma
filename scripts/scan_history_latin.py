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

# Split over short lines so this file's own source never has a line dense enough to be flagged.
WORDS = """quod est sed enim
autem ergo dicendum videtur
sicut igitur non esse
unde quia""".split()
LATIN_WORDS = re.compile(r"\b(" + "|".join(WORDS) + r")\b", re.IGNORECASE)
MIN_HITS = 6
# Its own word list matched in an earlier committed version; it never holds source text.
SELF = "scripts/scan_history_latin.py"


def suspicious_lines(text: str) -> list[str]:
    return [line for line in text.splitlines() if len(LATIN_WORDS.findall(line)) >= MIN_HITS and "fictus" not in line]


def main() -> int:
    objects = subprocess.run(["git", "rev-list", "--all", "--objects"], capture_output=True, text=True, check=True)
    found: dict[str, list[tuple[str, int]]] = {}
    for line in objects.stdout.splitlines():
        sha, _, path = line.partition(" ")
        if not path or path.startswith("data/hr/") or path == SELF:
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
