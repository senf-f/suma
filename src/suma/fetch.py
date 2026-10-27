import time
from pathlib import Path

import httpx

BASE_URL = "https://www.corpusthomisticum.org/"
USER_AGENT = "suma-pilot (personal research; contact via github.com/senf-f)"
PILOT_PAGES = ["sth1001.html", "sth1002.html", "sth1003.html"]


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
