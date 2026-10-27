import re
from urllib.parse import parse_qs, urlsplit

import pytest

from suma.glossary import write_draft
from suma.reader import build, issue_url
from suma.store import write_units

OPUS, SONNET = "claude-opus-5-5", "claude-sonnet-5-5"


@pytest.fixture
def site(latin_q2, tmp_path):
    hr = tmp_path / "hr"
    write_units(OPUS, "I", 2, {"I.q2.a3.sc": "Ali protiv toga: *Ja sam koji jesam*.", "I.q2.a3.ad1": "Na prvo"}, "1", 1, hr)
    write_units(SONNET, "I", 2, {"I.q2.a3.ad1": "Na prvo (S)"}, "1", 1, hr)
    glossary = tmp_path / "glossary.yaml"
    write_draft({"terms": [{"la": "esse", "hr": "bitak", "alternatives": ["biti"], "note": "čin"}]}, glossary)
    out = tmp_path / "dist"
    build(latin_q2, hr, glossary, out)
    return out


def page(site):
    return (site / "I" / "q002.html").read_text(encoding="utf-8")


def test_question_page_has_anchors_and_models(site):
    html = page(site)
    assert 'id="I.q2.a3.ad1"' in html
    assert f'data-model="{OPUS}"' in html
    assert f'data-model="{SONNET}"' in html
    assert "Na prvo (S)" in html
    assert "Odgovor na 1" in html
    assert "Članak 3" in html


def test_italics_rendered_and_escaped(site):
    html = page(site)
    assert "<em>Ja sam koji jesam</em>" in html
    assert "<em>ego sum qui sum</em>" in html


def test_html_in_text_is_escaped(latin_q2, tmp_path):
    hr = tmp_path / "hr"
    write_units(OPUS, "I", 2, {"I.q2.pr": "<script>alert(1)</script> *x*"}, "1", 1, hr)
    out = tmp_path / "dist"
    build(latin_q2, hr, tmp_path / "none.yaml", out)
    html = (out / "I" / "q002.html").read_text(encoding="utf-8")
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_links_are_relative(site):
    for path in site.rglob("*.html"):
        html = path.read_text(encoding="utf-8")
        assert not re.search(r'(href|src)="/', html), path
    assert 'href="../static/style.css"' in page(site)
    assert 'href="static/style.css"' in (site / "index.html").read_text(encoding="utf-8")
    assert (site / "static" / "style.css").exists()
    assert (site / "static" / "reader.js").exists()


def test_index_and_glossary(site):
    index = (site / "index.html").read_text(encoding="utf-8")
    assert 'href="I/q002.html"' in index
    assert 'href="I/q002.html#I.q2.a3"' in index
    glossary = (site / "glosar.html").read_text(encoding="utf-8")
    assert "esse" in glossary and "bitak" in glossary


def test_missing_translation_shows_placeholder(site):
    html = page(site)
    pr_row = html[html.index('id="I.q2.pr"'):html.index('id="I.q2.a3.obj1"')]
    assert "Prijevod još nije dostupan." in pr_row


def test_citation_attribute(site):
    assert 'data-cite="Toma Akvinski, Summa theologiae I, q. 2, a. 3, ad 1"' in page(site)


def body_of(url):
    query = parse_qs(urlsplit(url).query)
    return query["title"][0], query["body"][0], query


def test_issue_url_truncates_long_units():
    url = issue_url("senf-f/suma", "I.q2.a3.resp", "L" * 5000, "H" * 5000, OPUS,
                    "https://senf-f.github.io/suma/I/q002.html")
    assert len(url) < 8000
    title, body, _ = body_of(url)
    assert title == "[prijedlog] I q.2 a.3 odgovor"
    assert "…" in body
    assert "https://senf-f.github.io/suma/I/q002.html#I.q2.a3.resp" in body
    assert OPUS in body


def test_issue_url_encoding_roundtrip():
    hr = "Čini se & da\nnije \"tako\" #1"
    url = issue_url("senf-f/suma", "I.q2.a3.ad1", "Ad primum", hr, OPUS, "https://x/I/q002.html")
    assert url.startswith("https://github.com/senf-f/suma/issues/new?")
    title, body, query = body_of(url)
    assert hr in body
    assert query["labels"] == ["prijedlog"]
    assert title == "[prijedlog] I q.2 a.3 ad 1"
