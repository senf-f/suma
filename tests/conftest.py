from pathlib import Path

import pytest

from suma.parse import parse_page, write_latin

FIXTURE = Path(__file__).parent / "fixtures" / "sth_sample.html"


@pytest.fixture
def latin_q2(tmp_path) -> Path:
    """data/latin-style dir holding I/q002.json (prologue + article 3) built from the fixture page."""
    latin_dir = tmp_path / "latin"
    write_latin(parse_page(FIXTURE.read_bytes()), "I", 1, 13, latin_dir)
    return latin_dir
