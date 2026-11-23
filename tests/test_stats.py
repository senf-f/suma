import shutil
import subprocess

import pytest

from suma import cli
from suma.stats import MARKER, parse_output, remote_script, render_report, stats

GOACCESS = '<!DOCTYPE html><html><body><script>var d = "a & b";</script></body></html>'
REMOTE_OUT = f"{GOACCESS}\n\n{MARKER}\n      12\tHR\tZagreb\n       3\tHR\tSplit\n       5\tHR\tZagreb\n       2\t\t\n"


def fake_run(returncode=0, stdout=REMOTE_OUT, stderr=""):
    calls = []

    def run(cmd, **kwargs):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, returncode, stdout.encode("utf-8"), stderr.encode("utf-8"))

    run.calls = calls
    return run


def test_parse_output_sums_ips_per_city_most_first():
    report, cities = parse_output(REMOTE_OUT)
    assert report == GOACCESS
    assert cities == [(17, "HR", "Zagreb"), (3, "HR", "Split"), (2, "??", "unknown")]


def test_parse_output_without_marker_fails_loudly():
    with pytest.raises(SystemExit, match="goaccess"):
        parse_output("bash: goaccess: command not found")


def test_report_embeds_goaccess_escaped_and_lists_cities():
    page = render_report(GOACCESS, [(17, "HR", "Zagreb"), (3, "HR", "<b>")])
    assert 'srcdoc="&lt;!DOCTYPE html&gt;' in page
    assert "a &amp; b" in page and "&quot;" in page  # escaped, so the attribute can't end early
    assert "<td>Zagreb</td>" in page and "85.0%" in page
    assert "<td>&lt;b&gt;</td>" in page


def test_report_with_no_traffic():
    assert "0 page views" in render_report(GOACCESS, [])


def test_stats_writes_report(tmp_path):
    run = fake_run()
    out = stats("root@example.org", tmp_path / "r" / "stats.html", run=run)
    assert run.calls[0][:2] == ["ssh", "root@example.org"]
    assert "Zagreb" in out.read_text(encoding="utf-8")


def test_stats_fails_loudly_when_ssh_cannot_connect(tmp_path):
    with pytest.raises(SystemExit, match="ssh could not connect to root@example.org"):
        stats("root@example.org", tmp_path / "s.html", run=fake_run(returncode=255))
    assert not (tmp_path / "s.html").exists()


def test_stats_reports_server_error(tmp_path):
    with pytest.raises(SystemExit, match="Unable to open GeoIP2 database"):
        stats("h", tmp_path / "s.html", run=fake_run(returncode=1, stderr="Unable to open GeoIP2 database"))


@pytest.mark.skipif(shutil.which("bash") is None, reason="needs a shell to syntax-check")
def test_remote_script_is_valid_shell():
    assert subprocess.run(["bash", "-n", "-c", remote_script()]).returncode == 0


def test_cli_stats_defaults_to_root_at_site_host(monkeypatch, tmp_path):
    seen = {}
    monkeypatch.delenv("SUMA_STATS_HOST", raising=False)
    monkeypatch.setenv("SUMA_SITE_URL", "https://suma.example.org")
    monkeypatch.setattr("suma.stats.stats", lambda host, out: seen.update(host=host, out=out))
    cli.main(["stats", "--no-open", "--out", str(tmp_path / "x.html")])
    assert seen["host"] == "root@suma.example.org"
