import re
import time
from pathlib import Path

import httpx

BASE_URL = "https://www.corpusthomisticum.org/"
USER_AGENT = "suma-pilot (personal research; contact via github.com/senf-f)"
PILOT_PAGES = ["sth1001.html", "sth1002.html", "sth1003.html"]
# First page and file-name prefix of each Part, checked against the live site.
# I-II and II-II each start with a page holding only the Part's prologue (sth2000, sth3000); each chain
# ends where the next Part's prefix begins.
PARTS = {"I": ("sth1001.html", "sth1"), "I-II": ("sth2000.html", "sth2"), "II-II": ("sth3000.html", "sth3")}
_NEXT_LINK = re.compile(rb'HREF="([^"]+)"><IMG SRC="icons/ageultra\.gif"', re.IGNORECASE)


def next_page(html: bytes) -> str | None:
    """The page the "age ultra" (next) arrow points to, if any."""
    match = _NEXT_LINK.search(html)
    return match.group(1).decode("ascii") if match else None


def make_client() -> httpx.Client:
    return httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=60, follow_redirects=True)


def fetch_pages(
    pages: list[str],
    cache_dir: Path,
    client: httpx.Client,
    delay: float = 2.0,
    sleep=time.sleep,
) -> list[Path]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    downloaded = 0
    for page in pages:
        target = cache_dir / page
        paths.append(target)
        if target.exists():
            continue
        if downloaded:
            sleep(delay)
        response = client.get(BASE_URL + page)
        response.raise_for_status()
        partial = target.with_suffix(target.suffix + ".part")
        partial.write_bytes(response.content)
        partial.replace(target)
        downloaded += 1
    return paths


def fetch_part(
    part: str,
    cache_dir: Path,
    client: httpx.Client,
    delay: float = 2.0,
    sleep=time.sleep,
) -> list[Path]:
    """Follow the next-page links from a Part's first page until they leave the Part."""
    if part not in PARTS:
        raise ValueError(f"Unknown or unverified part {part!r}; known: {sorted(PARTS)}")
    page, prefix = PARTS[part]
    paths: list[Path] = []
    downloaded = 0
    while page and page.startswith(prefix) and cache_dir / page not in paths:
        if not (cache_dir / page).exists() and downloaded:
            sleep(delay)
        was_cached = (cache_dir / page).exists()
        [path] = fetch_pages([page], cache_dir, client, delay=delay, sleep=sleep)
        downloaded += not was_cached
        paths.append(path)
        page = next_page(path.read_bytes())
    return paths
