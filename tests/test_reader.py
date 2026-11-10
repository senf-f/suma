import re
from urllib.parse import parse_qs, unquote, urlsplit

import pytest

from suma.glossary import write_draft
from suma.reader import DEFAULT_SITE_URL, build, issue_url
from suma.store import write_units

OPUS, SONNET = "claude-opus-5-5", "claude-sonnet-5-5"


@pytest.fixture
def site(latin_q2, tmp_path):
    hr = tmp_path / "hr"
    write_units(OPUS, "I", 2, {"I.q2.a3.sc": "Ali protiv toga: *Ja sam koji jesam*.", "I.q2.a3.ad1": "Na prvo"}, "1", 1, hr)
    write_units(SONNET, "I", 2, {"I.q2.a3.ad1": "Na prvo (S)"}, "1", 1, hr)
    glossary = tmp_path / "glossary.yaml"
    write_draft({"terms": [
        {"la": "esse", "hr": "bitak", "alternatives": ["biti"], "note": "translator only",
         "opis": "Čin postojanja, različit od *ens*.", "mjesto": "I.q2.a3.ad1"},
        {"la": "book titles", "hr": "-", "alternatives": [], "note": "meta", "opis": None, "mjesto": None},
        {"la": "consilium (deliberation)", "prikaz": "consilium", "hr": "promišljanje", "alternatives": []},
    ]}, glossary)
    out = tmp_path / "dist"
    build(latin_q2, hr, glossary, out)
    return out


@pytest.fixture
def site_with_latin(latin_q2, tmp_path):
    hr = tmp_path / "hr"
    write_units(OPUS, "I", 2, {"I.q2.a3.ad1": "Na prvo"}, "1", 1, hr)
    write_units(SONNET, "I", 2, {"I.q2.a3.ad1": "Na prvo (S)"}, "1", 1, hr)
    out = tmp_path / "dist-la"
    build(latin_q2, hr, tmp_path / "none.yaml", out, with_latin=True)
    return out


def page(site):
    return (site / "I" / "q002.html").read_text(encoding="utf-8")


def latin_page(site):
    return page(site)


def test_question_page_has_anchors(site):
    html = page(site)
    assert 'id="I.q2.a3.ad1"' in html
    assert f'data-model="{OPUS}"' in html
    assert "Odgovor na 1" in html
    assert "Članak 3" in html


def test_public_site_shows_only_public_models(site):
    """Sonnet covers only q.1-13; on the public site it would mostly show empty placeholders."""
    html = page(site)
    assert f'data-model="{SONNET}"' not in html
    assert "Na prvo (S)" not in html
    assert 'id="model-switch"' not in html, "one model left, so no switch"


def test_local_review_build_keeps_every_model(site_with_latin):
    html = page(site_with_latin)
    assert f'data-model="{OPUS}"' in html and f'data-model="{SONNET}"' in html
    assert "Na prvo (S)" in html
    assert 'id="model-switch"' in html


def test_italics_rendered_and_escaped(site, site_with_latin):
    assert "<em>Ja sam koji jesam</em>" in page(site)
    assert "<em>verba ficta ad probandum</em>" in latin_page(site_with_latin)


def test_public_build_contains_no_latin_text(site):
    # Corpus Thomisticum permits publishing the translation but not its Latin text.
    for path in site.rglob("*"):
        if path.is_file() and path.suffix in {".html", ".js", ".json"}:
            text = unquote(path.read_text(encoding="utf-8")).lower()
            assert "textus fictus" not in text, path
            assert "verba ficta" not in text, path
    assert 'id="latin-toggle"' not in page(site)
    assert 'class="la-btn"' not in page(site)


def test_units_link_to_latin_passage(site):
    html = page(site)
    assert 'href="https://www.corpusthomisticum.org/sth1002.html#28319"' in html
    assert "Latinski izvornik" in html


def test_local_build_with_latin_shows_parallel_text(site_with_latin):
    html = latin_page(site_with_latin)
    assert 'id="latin-toggle"' in html
    assert "Praeterea, textus fictus secundae obiectionis." in html


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
        if path.name == "404.html":  # served by the web server at any URL, so its links are absolute
            continue
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


def test_glossary_shows_reader_description_not_translator_note(site):
    glossary = (site / "glosar.html").read_text(encoding="utf-8")
    assert "Čin postojanja, različit od <em>ens</em>." in glossary
    assert "translator only" not in glossary
    assert 'href="I/q002.html#I.q2.a3.ad1"' in glossary
    assert "I, q. 2, a. 3, ad 1" in glossary
    assert "book titles" not in glossary
    assert "consilium" in glossary and "deliberation" not in glossary


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
    url = issue_url("senf-f/suma", "I.q2.a3.resp", "https://www.corpusthomisticum.org/sth1002.html#28318",
                    "H" * 5000, OPUS, "https://senf-f.github.io/suma/I/q002.html")
    assert len(url) < 8000
    title, body, _ = body_of(url)
    assert title == "[prijedlog] I q.2 a.3 odgovor"
    assert "…" in body
    assert "https://senf-f.github.io/suma/I/q002.html#I.q2.a3.resp" in body
    assert OPUS in body
    assert "https://www.corpusthomisticum.org/sth1002.html#28318" in body


def test_issue_url_encoding_roundtrip():
    hr = "Čini se & da\nnije \"tako\" #1"
    url = issue_url("senf-f/suma", "I.q2.a3.ad1", "https://ct/sth1002.html#1", hr, OPUS, "https://x/I/q002.html")
    assert url.startswith("https://github.com/senf-f/suma/issues/new?")
    title, body, query = body_of(url)
    assert hr in body
    assert query["labels"] == ["prijedlog"]
    assert title == "[prijedlog] I q.2 a.3 ad 1"


def test_issue_links_use_site_url(latin_q2, tmp_path):
    hr = tmp_path / "hr"
    write_units(OPUS, "I", 2, {"I.q2.a3.ad1": "Na prvo"}, "1", 1, hr)
    build(latin_q2, hr, tmp_path / "none.yaml", tmp_path / "out", site_url="https://suma.example.hr")
    html = unquote((tmp_path / "out" / "I" / "q002.html").read_text(encoding="utf-8"))
    assert "https://suma.example.hr/I/q002.html" in html
    assert "github.io" not in html


def test_default_site_url_is_the_live_subdomain():
    assert DEFAULT_SITE_URL == "https://suma.oprobate.eu"


def test_404_page_uses_absolute_links(site):
    html = (site / "404.html").read_text(encoding="utf-8")
    assert "Stranica nije pronađena" in html
    assert 'href="/index.html"' in html and 'href="/static/style.css"' in html


def test_pages_link_a_favicon(site):
    assert 'href="static/favicon.svg"' in (site / "index.html").read_text(encoding="utf-8")
    assert (site / "static" / "favicon.svg").exists()
