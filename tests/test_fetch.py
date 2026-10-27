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
