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


def _capture_build(monkeypatch):
    import subprocess

    import suma.reader

    calls = []
    monkeypatch.setattr(suma.reader, "build", lambda *a, **kw: calls.append(kw))
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: None)
    return calls


def test_build_passes_site_url(monkeypatch, tmp_path):
    calls = _capture_build(monkeypatch)
    cli.main(["build", "--out", str(tmp_path / "out"), "--site-url", "https://x.test"])
    assert calls[0]["site_url"] == "https://x.test"


def test_build_site_url_defaults_to_env(monkeypatch, tmp_path):
    calls = _capture_build(monkeypatch)
    monkeypatch.setenv("SUMA_SITE_URL", "https://env.test")
    cli.main(["build", "--out", str(tmp_path / "out")])
    assert calls[0]["site_url"] == "https://env.test"
