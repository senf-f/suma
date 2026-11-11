import httpx
import pytest

from suma.fetch import fetch_pages


def make_client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_fetch_downloads_and_caches(tmp_path):
    requested = []

    def handler(request):
        requested.append(request.url.path)
        return httpx.Response(200, content=b"page " + request.url.path.encode())

    sleeps = []
    pages = ["a.html", "b.html", "c.html"]
    paths = fetch_pages(pages, tmp_path, make_client(handler), sleep=sleeps.append)

    assert [p.name for p in paths] == pages
    assert (tmp_path / "b.html").read_bytes() == b"page /b.html"
    assert requested == ["/a.html", "/b.html", "/c.html"]
    assert len(sleeps) == 2


def test_fetch_skips_cached(tmp_path):
    (tmp_path / "a.html").write_bytes(b"cached")
    requested = []

    def handler(request):
        requested.append(request.url.path)
        return httpx.Response(200, content=b"new")

    fetch_pages(["a.html", "b.html", "c.html"], tmp_path, make_client(handler), sleep=lambda s: None)

    assert requested == ["/b.html", "/c.html"]
    assert (tmp_path / "a.html").read_bytes() == b"cached"


def test_fetch_raises_on_http_error(tmp_path):
    client = make_client(lambda request: httpx.Response(404))

    with pytest.raises(httpx.HTTPStatusError):
        fetch_pages(["missing.html"], tmp_path, client, sleep=lambda s: None)

    assert list(tmp_path.iterdir()) == []


NAV = (
    b'<P>\n<A HREF="{prev}"><IMG SRC="icons/ageretro.gif" ALT="age retro"></A>\n&nbsp;\n'
    b'<A HREF="{next}"><IMG SRC="icons/ageultra.gif" ALT="age ultra"></A>'
)


def nav(prev: str, nxt: str) -> bytes:
    return NAV.replace(b"{prev}", prev.encode()).replace(b"{next}", nxt.encode())


def test_next_page_reads_age_ultra_link():
    from suma.fetch import next_page

    assert next_page(nav("sth1002.html", "sth1015.html")) == "sth1015.html"
    assert next_page(b"<P>no navigation here</P>") is None


def test_fetch_part_follows_chain_and_stops_at_next_part(tmp_path):
    from suma.fetch import fetch_part

    site = {
        "sth1001.html": nav("index.html", "sth1002.html"),
        "sth1002.html": nav("sth1001.html", "sth1003.html"),
        "sth1003.html": nav("sth1002.html", "sth2001.html"),
    }
    requested = []

    def handler(request):
        page = request.url.path.lstrip("/")
        requested.append(page)
        return httpx.Response(200, content=site[page])

    (tmp_path / "sth1001.html").write_bytes(site["sth1001.html"])  # cached: read, not refetched
    sleeps = []
    paths = fetch_part("I", tmp_path, make_client(handler), sleep=sleeps.append)

    assert [p.name for p in paths] == ["sth1001.html", "sth1002.html", "sth1003.html"]
    assert requested == ["sth1002.html", "sth1003.html"]
    assert len(sleeps) == 1


def test_fetch_part_rejects_unknown_part(tmp_path):
    from suma.fetch import fetch_part

    with pytest.raises(ValueError):
        fetch_part("II-II", tmp_path, make_client(lambda r: httpx.Response(404)))


def test_fetch_part_prima_secundae_starts_at_its_prologue_page(tmp_path):
    from suma.fetch import fetch_part

    site = {
        "sth2000.html": nav("sth1103.html", "sth2001.html"),
        "sth2001.html": nav("sth2000.html", "sth3000.html"),
    }
    paths = fetch_part("I-II", tmp_path, make_client(lambda r: httpx.Response(200, content=site[r.url.path.lstrip("/")])),
                       sleep=lambda s: None)

    assert [p.name for p in paths] == ["sth2000.html", "sth2001.html"]
