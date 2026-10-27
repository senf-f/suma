import io
import sys

import pytest

from suma import cli


def test_console_switched_to_utf8(monkeypatch):
    cp1250 = io.TextIOWrapper(io.BytesIO(), encoding="cp1250")
    monkeypatch.setattr(sys, "stdout", cp1250)

    with pytest.raises(SystemExit):
        cli.main(["--help"])

    assert sys.stdout.encoding.lower() == "utf-8"
    print("≈ čćžšđ")
