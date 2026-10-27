import json
from pathlib import Path

import pytest

from suma.parse import parse_page, write_latin

FIXTURE = Path(__file__).parent / "fixtures" / "sth_sample.html"


@pytest.fixture
def units():
    return parse_page(FIXTURE.read_bytes())


def test_parse_ids_in_order(units):
    assert [u["id"] for u in units] == [
        "I.q2.pr",
        "I.q2.a3.obj1",
        "I.q2.a3.obj2",
        "I.q2.a3.sc",
        "I.q2.a3.resp",
        "I.q2.a3.ad1",
        "I.q2.a3.ad2",
        "I.q14.a1.obj1",
    ]
    assert [u["kind"] for u in units[:5]] == ["pr", "obj", "obj", "sc", "resp"]


def test_ref_span_removed(units):
    for u in units:
        assert "[28" not in u["text"]
        assert "Iª q." not in u["text"]
    assert units[1]["text"].startswith("Ad tertium sic proceditur.")


def test_italics_become_asterisks(units):
    sc = units[3]["text"]
    assert sc == "Sed contra est quod dicitur Exodi III, ex persona Dei, *ego sum qui sum*."


def test_entities_and_latin1_decoded():
    html = '<P TITLE="I q. 3 pr.">Caes&aacute;r \xe6qualis\n  dixit.</P>'.encode("iso-8859-1")
    [unit] = parse_page(html)
    assert unit["text"] == "Caesár æqualis dixit."


def test_write_latin_respects_range(units, tmp_path):
    written = write_latin(units, "I", 1, 13, tmp_path)

    assert [p.relative_to(tmp_path).as_posix() for p in written] == ["I/q002.json"]
    assert not (tmp_path / "I" / "q014.json").exists()
    data = json.loads((tmp_path / "I" / "q002.json").read_text(encoding="utf-8"))
    assert data["id"] == "I.q2"
    assert data["part"] == "I"
    assert data["question"] == 2
    assert len(data["units"]) == 7


def test_kind_for_reply_to_all_and_numbered_sed_contra():
    html = b'<P TITLE="I q. 1 a. 4 ad arg.">x</P><P TITLE="I q. 3 a. 2 s. c. 2">y</P>'
    assert [u["kind"] for u in parse_page(html)] == ["ad", "sc"]


def test_unknown_label_raises():
    with pytest.raises(ValueError):
        parse_page(b'<P TITLE="I q. 2 a. 3 xyz">text</P>')
