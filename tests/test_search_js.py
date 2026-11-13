"""The search box's matching rule (src/suma/reader_static/search.js), run under Node.

Pagefind falls back to a shorter prefix when a word has no match (searching "supplementum" returns pages
with "su"). The rule decides whether the words Pagefind highlighted are close enough to what was typed.
"""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

SEARCH_JS = Path(__file__).parent.parent / "src" / "suma" / "reader_static" / "search.js"

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


def accepts(query, marked):
    script = (f"const s = require({json.dumps(str(SEARCH_JS))});"
              f"process.stdout.write(JSON.stringify(s.accepts({json.dumps(query)}, {json.dumps(marked)})));")
    return json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)


def test_rejects_a_far_shorter_fallback_prefix():
    assert accepts("supplementum", ["su"]) is False
    assert accepts("xyzqw", ["X."]) is False


def test_accepts_the_word_itself_and_longer_forms():
    assert accepts("sakrament", ["sakrament;", "sakramenta"]) is True
    assert accepts("pretvor", ["pretvorba"]) is True


def test_accepts_a_fallback_to_a_close_stem():
    # an inflected form missing from the index falls back to its stem
    assert accepts("sakramentima", ["sakrament"]) is True


def test_ignores_case_and_diacritics():
    assert accepts("bogostovlje", ["Bogoštovlje"]) is True
    assert accepts("Đavao", ["đavao,"]) is True


def test_every_word_of_the_query_must_match():
    assert accepts("milost glave", ["milost", "Glave"]) is True
    assert accepts("milost supplementum", ["milost", "su"]) is False


def test_matched_words_come_from_every_match_on_the_page_not_just_the_excerpt():
    script = (f"const s = require({json.dumps(str(SEARCH_JS))});"
              "const data = {content: 'Kristova milost Glave i milost sjedinjenja', locations: [1, 2, 4]};"
              "process.stdout.write(JSON.stringify(s.matchedWords(data)));")
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout
    assert json.loads(out) == ["milost", "Glave", "milost"]


def test_short_queries_are_left_to_pagefind():
    assert accepts("su", ["su"]) is True
    assert accepts("bog", ["Bog"]) is True
