import re
from pathlib import Path
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
    assert 'href="../static/style.css?v=' in page(site)
    assert 'href="static/style.css?v=' in (site / "index.html").read_text(encoding="utf-8")
    assert (site / "static" / "style.css").exists()
    assert (site / "static" / "reader.js").exists()


def test_index_and_glossary(site):
    contents = (site / "sadrzaj.html").read_text(encoding="utf-8")
    assert 'href="I/q002.html"' in contents
    assert 'href="I/q002.html#I.q2.a3"' in contents
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


TEMPLATE = Path(__file__).parent.parent / ".github" / "ISSUE_TEMPLATE" / "prijedlog.yml"


def fields_of(url):
    return {k: v[0] for k, v in parse_qs(urlsplit(url).query).items()}


def test_issue_url_truncates_long_units():
    url = issue_url("senf-f/suma", "I.q2.a3.resp", "https://www.corpusthomisticum.org/sth1002.html#28318",
                    "H" * 5000, OPUS, "https://senf-f.github.io/suma/I/q002.html")
    assert len(url) < 8000
    fields = fields_of(url)
    assert fields["title"] == "[prijedlog] I q.2 a.3 odgovor"
    assert fields["trenutni"].endswith("…")
    assert fields["poveznica"] == "https://senf-f.github.io/suma/I/q002.html#I.q2.a3.resp"
    assert fields["model"] == OPUS
    assert fields["izvornik"] == "https://www.corpusthomisticum.org/sth1002.html#28318"


def test_issue_url_encoding_roundtrip():
    hr = "Čini se & da\nnije \"tako\" #1"
    url = issue_url("senf-f/suma", "I.q2.a3.ad1", "https://ct/sth1002.html#1", hr, OPUS, "https://x/I/q002.html")
    assert url.startswith("https://github.com/senf-f/suma/issues/new?")
    fields = fields_of(url)
    assert fields["trenutni"] == hr
    assert fields["jedinica"] == "I.q2.a3.ad1"
    assert fields["title"] == "[prijedlog] I q.2 a.3 ad 1"


def test_issue_url_opens_the_suggestion_form():
    """An issue form labels every suggestion; a labels= link parameter only works for repo collaborators."""
    fields = fields_of(issue_url("senf-f/suma", "I.q2.a3.ad1", "https://ct/1", "Na prvo", OPUS, "https://x/I/q002.html"))
    assert fields["template"] == TEMPLATE.name


def test_suggestion_form_matches_issue_links():
    import yaml

    form = yaml.safe_load(TEMPLATE.read_text(encoding="utf-8"))
    assert form["labels"] == ["prijedlog"]
    ids = {item["id"] for item in form["body"] if "id" in item}
    prefilled = set(fields_of(issue_url("senf-f/suma", "I.q2.a3.ad1", "https://ct/1", "x", OPUS, "https://x/q")))
    assert prefilled - {"template", "title"} <= ids, "every prefilled field must exist in the form"
    assert {"prijedlog", "obrazlozenje"} <= ids


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
    assert 'href="/index.html"' in html and 'href="/static/style.css?v=' in html


def test_pages_link_a_favicon(site):
    assert 'href="static/favicon.svg?v=' in (site / "index.html").read_text(encoding="utf-8")
    assert (site / "static" / "favicon.svg").exists()


def test_home_page_explains_the_project_and_how_to_contribute(site):
    home = (site / "index.html").read_text(encoding="utf-8")
    assert "Kako pomoći" in home
    assert "Predloži poboljšanje" in home  # names the button readers will look for
    assert 'href="https://github.com/senf-f/suma"' in home
    assert 'href="sadrzaj.html"' in home and 'href="glosar.html"' in home
    assert "Prvi dio: 1 pitanje" in home  # what is available so far, counted from the build


def test_search_loads_pagefind_from_a_full_url(site):
    # import() rejects a bare "pagefind/pagefind.js" on top-level pages, where SUMA_ROOT is "".
    js = (site / "static" / "reader.js").read_text(encoding="utf-8")
    assert 'new URL((window.SUMA_ROOT || "") + "pagefind/pagefind.js", document.baseURI).href' in js


def test_search_box_is_our_own_and_filters_prefix_fallbacks(site):
    html = (site / "index.html").read_text(encoding="utf-8")
    assert "pagefind-ui" not in html  # Pagefind's ready-made UI cannot drop fallback results
    assert 'src="static/search.js?v=' in html and html.index("search.js") < html.index("reader.js")
    js = (site / "static" / "reader.js").read_text(encoding="utf-8")
    assert "SumaSearch.accepts(" in js
    assert (site / "static" / "search.js").exists()


def test_footer_does_not_call_the_translation_a_pilot(site):
    footer = (site / "index.html").read_text(encoding="utf-8").split('<footer class="site">')[1]
    assert "pilot" not in footer and "u izradi" not in footer


def test_home_page_does_not_promise_more_parts(site):
    home = (site / "index.html").read_text(encoding="utf-8")
    assert "slijede" not in home and "u nastajanju" not in home  # the whole Summa is translated
    assert "Dopuna" in home  # says why the Supplementum is not included


def test_question_count_is_declined():
    from suma.reader import count_questions
    assert [count_questions(n) for n in (1, 2, 5, 11, 21, 119)] == [
        "1 pitanje", "2 pitanja", "5 pitanja", "11 pitanja", "21 pitanje", "119 pitanja"]


def test_home_page_does_not_promise_latin_text(site):
    """The public site never shows the Latin; it only links to Corpus Thomisticum."""
    home = (site / "index.html").read_text(encoding="utf-8")
    assert "uz latinski izvornik" not in home.lower()


def test_header_links_home_and_contents(site):
    html = page(site)
    assert 'href="../index.html">Početna' in html
    assert 'href="../sadrzaj.html">Sadržaj' in html


def test_home_page_offers_email_contact(site):
    home = (site / "index.html").read_text(encoding="utf-8")
    assert 'href="mailto:oprobate@proton.me"' in home
    assert "Kontakt" in home


def test_footer_links_email_contact(site):
    assert 'href="mailto:oprobate@proton.me"' in page(site)


# --- reading layout: quiet paragraphs (A), calm header (B), centred column and navigation (C) ---

def unit_block(html, unit_id):
    start = html.index(f'<div class="unit" id="{unit_id}"')
    return html[start:html.index('<div class="unit"', start + 1) if '<div class="unit"' in html[start + 1:] else len(html)]


def test_paragraph_actions_sit_behind_one_toggle(site):
    block = unit_block(page(site), "I.q2.a3.ad1")
    assert 'class="more" aria-expanded="false" aria-controls="act-I.q2.a3.ad1"' in block
    actions = block[block.index('id="act-I.q2.a3.ad1"'):]
    assert "Kopiraj citat" in actions and "Latinski izvornik" in actions and "Predloži poboljšanje" in actions
    assert "data-pagefind-ignore" in block[:block.index("<p>")], "action labels stay out of the search index"


def test_answer_label_is_marked(site):
    html = page(site)
    assert 'class="label answer" href="#I.q2.a3.resp"' in html
    assert 'class="label" href="#I.q2.a3.ad1"' in html


def test_question_lists_its_articles_on_top(site):
    html = page(site)
    nav = html[html.index('<nav class="on-page"'):]
    assert 'href="#I.q2.a3">Članak 3</a>' in nav[:nav.index("</nav>")]


def test_article_heading_counts_articles(site):
    assert '<h2>Članak 3 <span class="of">od 3</span></h2>' in page(site)


def test_header_has_search_and_theme_buttons(site):
    html = page(site)
    assert 'id="search-toggle" aria-expanded="false" aria-controls="search"' in html
    assert 'id="theme-toggle"' in html
    assert '<div id="search" hidden>' in html


def test_saved_theme_applies_before_first_paint(site):
    html = page(site)
    head = html[:html.index("</head>")]
    assert "suma.theme" in head and "data-theme" in head


def test_pager_names_neighbouring_questions(latin_q2, tmp_path):
    import json

    q2 = latin_q2 / "I" / "q002.json"
    q3 = json.loads(q2.read_text(encoding="utf-8").replace("I.q2", "I.q3"))
    q3["question"] = 3
    (latin_q2 / "I" / "q003.json").write_text(json.dumps(q3), encoding="utf-8")
    write_units(OPUS, "I", 2, {"I.q2.pr": "Uvod"}, "1", 1, tmp_path / "hr")
    write_units(OPUS, "I", 3, {"I.q3.pr": "Uvod"}, "1", 1, tmp_path / "hr")
    out = tmp_path / "out"
    build(latin_q2, tmp_path / "hr", tmp_path / "none.yaml", out)
    html = (out / "I" / "q002.html").read_text(encoding="utf-8")
    pager = html[html.index('<nav class="pager"'):]
    assert 'href="../I/q003.html"' in pager and "Pitanje 3" in pager and "Sljedeće" in pager


def test_static_assets_carry_a_content_version(site):
    """Pages are revalidated on every visit but assets are cached for an hour, so a new deploy must change
    the asset URLs; otherwise a returning reader gets new pages with the old script and nothing responds."""
    html = page(site)
    version = re.search(r'static/reader\.js\?v=([0-9a-f]{10})"', html).group(1)
    assert f'static/style.css?v={version}"' in html


def test_asset_version_changes_with_asset_content(latin_q2, tmp_path, monkeypatch):
    import suma.reader

    write_units(OPUS, "I", 2, {"I.q2.pr": "Uvod"}, "1", 1, tmp_path / "hr")

    def version_of(out):
        build(latin_q2, tmp_path / "hr", tmp_path / "none.yaml", out)
        return re.search(r"reader\.js\?v=(\w+)", (out / "I" / "q002.html").read_text(encoding="utf-8")).group(1)

    first = version_of(tmp_path / "a")
    assert version_of(tmp_path / "b") == first, "same files, same version"
    static = tmp_path / "static"
    import shutil
    shutil.copytree(suma.reader.STATIC_DIR, static)
    (static / "reader.js").write_text("// changed", encoding="utf-8")
    monkeypatch.setattr(suma.reader, "STATIC_DIR", static)
    assert version_of(tmp_path / "c") != first


@pytest.fixture
def site_with_prologue(latin_q2, tmp_path):
    import json

    (latin_q2 / "I-II").mkdir()
    (latin_q2 / "I-II" / "q000.json").write_text(json.dumps({
        "id": "I-II.pr", "part": "I-II", "question": 0,
        "units": [{"id": "I-II.pr", "kind": "pr", "text": "Prologus", "source": "https://x/sth2000.html#1"}],
    }), encoding="utf-8")
    (latin_q2 / "I-II" / "q001.json").write_text(json.dumps({
        "id": "I-II.q1", "part": "I-II", "question": 1,
        "units": [{"id": "I-II.q1.pr", "kind": "pr", "text": "Uvod", "source": "https://x/sth2001.html#1"}],
    }), encoding="utf-8")
    (latin_q2 / "I-II" / "q002.json").write_text(json.dumps({
        "id": "I-II.q2", "part": "I-II", "question": 2,
        "units": [{"id": "I-II.q2.pr", "kind": "pr", "text": "Uvod", "source": "https://x/sth2001.html#9"}],
    }), encoding="utf-8")
    hr = tmp_path / "hr"
    write_units(OPUS, "I", 2, {"I.q2.pr": "Uvod"}, "1", 1, hr)
    write_units(OPUS, "I-II", 0, {"I-II.pr": "Budući da je čovjek stvoren na sliku Božju"}, "1", 1, hr)
    write_units(OPUS, "I-II", 1, {"I-II.q1.pr": "Uvod u prvo pitanje"}, "1", 1, hr)
    out = tmp_path / "dist"
    build(latin_q2, hr, tmp_path / "none.yaml", out)
    return out


def test_part_prologue_has_its_own_page(site_with_prologue):
    html = (site_with_prologue / "I-II" / "prolog.html").read_text(encoding="utf-8")
    assert "<h1>Prolog</h1>" in html
    assert 'id="I-II.pr"' in html
    assert "Budući da je čovjek stvoren na sliku Božju" in html
    assert 'data-cite="Toma Akvinski, Summa theologiae I-II, prol."' in html
    assert "Prologus" not in html  # Latin never reaches the public site
    assert not (site_with_prologue / "I-II" / "q000.html").exists()


def test_part_prologue_heads_its_part_in_the_contents(site_with_prologue):
    html = (site_with_prologue / "sadrzaj.html").read_text(encoding="utf-8")
    part = html[html.index("Prvi dio Drugoga dijela"):]
    assert part.index('href="I-II/prolog.html"') < part.index('href="I-II/q001.html"')


def test_part_prologue_sits_between_parts_in_the_pager(site_with_prologue):
    prologue = (site_with_prologue / "I-II" / "prolog.html").read_text(encoding="utf-8")
    pager = prologue[prologue.index('<nav class="pager"'):]
    assert 'href="../I/q002.html"' in pager and 'href="../I-II/q001.html"' in pager
    q1 = (site_with_prologue / "I-II" / "q001.html").read_text(encoding="utf-8")
    assert 'href="../I-II/prolog.html"' in q1 and ">Prolog</a>" in q1


def test_part_prologue_is_not_counted_as_a_question(site_with_prologue):
    html = (site_with_prologue / "index.html").read_text(encoding="utf-8")
    assert html.count("1 pitanje") == 2  # I: q.2 only; I-II: q.1 only


def test_part_prologue_suggestion_link():
    url = issue_url("o/r", "I-II.pr", "https://x/sth2000.html#1", "tekst", OPUS, "https://s/I-II/prolog.html")
    assert "title=%5Bprijedlog%5D%20I-II%20prolog" in url


def test_public_site_leaves_out_untranslated_questions(site_with_prologue):
    """Latin is parsed ahead of translating; until a question has a translation it stays off the public site."""
    assert not (site_with_prologue / "I-II" / "q002.html").exists()
    assert 'href="I-II/q002.html"' not in (site_with_prologue / "sadrzaj.html").read_text(encoding="utf-8")
    pager = (site_with_prologue / "I-II" / "prolog.html").read_text(encoding="utf-8")
    assert "I-II/q002.html" not in pager


def test_local_review_build_keeps_untranslated_questions(site_with_prologue, latin_q2, tmp_path):
    out = tmp_path / "review"
    build(latin_q2, tmp_path / "hr", tmp_path / "none.yaml", out, with_latin=True)
    assert (out / "I-II" / "q002.html").exists()
