import re

import pytest

from suma.ids import article_of, custom_id, label_to_id, parse_range


@pytest.mark.parametrize(
    "label, expected",
    [
        ("I q. 2 a. 1 arg. 1", "I.q2.a1.obj1"),
        ("I q. 2 pr.", "I.q2.pr"),
        ("I q. 2 a. 3 s. c.", "I.q2.a3.sc"),
        ("I q. 2 a. 3 co.", "I.q2.a3.resp"),
        ("I q. 2 a. 3 ad 3", "I.q2.a3.ad3"),
        ("I-II q. 90 a. 4 co.", "I-II.q90.a4.resp"),
        ("I q. 1 a. 4 ad arg.", "I.q1.a4.adarg"),
        ("I q. 3 a. 2 s. c. 2", "I.q3.a2.sc2"),
    ],
)
def test_label_to_id(label, expected):
    assert label_to_id(label) == expected


def test_label_to_id_rejects_unknown():
    with pytest.raises(ValueError):
        label_to_id("I q. 2 a. 1 foo")


def test_article_of():
    assert article_of("I.q2.a3.ad1") == "I.q2.a3"
    assert article_of("I.q2.pr") == "I.q2.pr"


def test_parse_range():
    assert parse_range("I.q1-13") == ("I", 1, 13)
    assert parse_range("I.q5") == ("I", 5, 5)


def test_custom_id_is_batch_safe():
    cid = custom_id("I.q2.a3")
    assert cid == "I-q2-a3"
    assert re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", cid)
