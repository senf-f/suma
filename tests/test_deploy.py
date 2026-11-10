import io
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest

from suma import cli
from suma.deploy import deploy, release_name, remote_script

NOW = datetime(2026, 11, 5, 12, 0, 0, tzinfo=timezone.utc)
RELEASE = "20261105T120000Z"


class Recorder:
    """Stands in for build, subprocess.run and subprocess.Popen; records what deploy asked for."""

    def __init__(self, ssh_returncode=0, tar_returncode=0):
        self.builds, self.runs = [], []
        self.ssh_returncode, self.tar_returncode = ssh_returncode, tar_returncode

    def build(self, latin_dir, hr_dir, glossary_path, out_dir, **kwargs):
        self.builds.append({"out_dir": Path(out_dir), "existed": Path(out_dir).exists(), **kwargs})
        Path(out_dir).mkdir(parents=True)
        (Path(out_dir) / "index.html").write_text("ok", encoding="utf-8")

    def run(self, cmd, **kwargs):
        self.runs.append(cmd)
        returncode = {"ssh": self.ssh_returncode, "tar": self.tar_returncode}.get(cmd[0], 0)
        if cmd[0] == "tar" and returncode == 0:
            Path(cmd[2]).write_bytes(b"archive")  # like real tar -czf <file>
        return subprocess.CompletedProcess(cmd, returncode)

    def tar_calls(self):
        return [c for c in self.runs if c[0] == "tar"]

    def ssh_calls(self):
        return [c for c in self.runs if c[0] == "ssh"]


def run_deploy(rec, tmp_path, **overrides):
    kwargs = dict(
        host="deploy@suma.example.hr",
        remote_path="/srv/suma",
        site_url="https://suma.example.hr",
        data_dir=tmp_path / "data",
        build_fn=rec.build,
        run=rec.run,
        now=lambda: NOW,
    )
    return deploy(**{**kwargs, **overrides})


def test_release_name_is_utc_timestamp():
    assert release_name(NOW) == RELEASE


def test_remote_script_swaps_only_after_extract():
    script = remote_script("/srv/suma", RELEASE)
    assert script.startswith("set -eu")
    assert "R=/srv/suma/releases/20261105T120000Z" in script
    extract = script.index('tar -xzf - -C "$R.partial"')
    rename = script.index('mv "$R.partial" "$R"')
    link = script.index('ln -sfn "$R" /srv/suma/current.tmp')
    swap = script.index("mv -T /srv/suma/current.tmp /srv/suma/current")
    assert extract < rename < link < swap


def test_remote_script_keeps_five_releases():
    script = remote_script("/srv/suma", RELEASE)
    # by name, not mtime: tar restores the archive's old mtimes onto each release directory
    assert 'ls -1d /srv/suma/releases/*/ | sort -r | grep -vxF "$R/" | tail -n +5' in script  # 4 others + the new one
    assert "ls -1dt" not in script
    assert script.index("mv -T") < script.index("tail -n +5")


def test_remote_script_announces_switch_before_pruning():
    script = remote_script("/srv/suma", RELEASE)
    assert script.index("mv -T") < script.index("echo deployed 20261105T120000Z") < script.index("tail -n +5")


def test_remote_script_prune_is_non_fatal_and_spares_the_new_release():
    prune = next(line for line in remote_script("/srv/suma", RELEASE).splitlines() if "tail -n +5" in line)
    assert 'grep -vxF "$R/"' in prune
    assert prune.rstrip().endswith("|| echo 'warning: pruning old releases failed'")


def test_deploy_builds_fresh_public_site(tmp_path):
    rec = Recorder()
    assert run_deploy(rec, tmp_path) == RELEASE
    [call] = rec.builds
    assert call["with_latin"] is False
    assert call["site_url"] == "https://suma.example.hr"
    assert not call["existed"]
    assert call["out_dir"].name not in ("dist", "dist-la")
    assert not call["out_dir"].exists(), "temporary build directory is removed afterwards"


def test_deploy_indexes_then_streams_to_ssh(tmp_path):
    rec = Recorder()
    run_deploy(rec, tmp_path)
    pagefind = rec.runs[0]
    assert pagefind[-3:-1] == ["pagefind", "--site"]
    [tar] = rec.tar_calls()
    assert tar[:2] == ["tar", "-czf"] and tar[2].endswith(".tgz") and tar[-1] == "."
    [ssh] = rec.ssh_calls()
    assert ssh[:2] == ["ssh", "deploy@suma.example.hr"]
    assert RELEASE in ssh[2] and ssh[2].startswith("sh -c ")


def test_deploy_rejects_non_https_site_url(tmp_path):
    rec = Recorder()
    with pytest.raises(SystemExit, match="https"):
        run_deploy(rec, tmp_path, site_url="http://suma.example.hr")
    assert rec.builds == []


def test_deploy_reports_connection_failure(tmp_path):
    rec = Recorder(ssh_returncode=255)
    with pytest.raises(SystemExit) as exc:
        run_deploy(rec, tmp_path)
    message = str(exc.value)
    assert "could not connect" in message and "deploy@suma.example.hr" in message
    assert "tar" not in message


def test_deploy_remote_failure_does_not_claim_nothing_changed(tmp_path):
    rec = Recorder(ssh_returncode=1)
    with pytest.raises(SystemExit) as exc:
        run_deploy(rec, tmp_path)
    message = str(exc.value)
    assert "nothing changed" not in message
    assert "deployed 20261105T120000Z" in message  # tells the owner which line proves the switch happened


def test_deploy_fails_when_local_tar_fails(tmp_path):
    rec = Recorder(tar_returncode=1)
    with pytest.raises(SystemExit, match="tar failed; nothing was uploaded"):
        run_deploy(rec, tmp_path)
    assert rec.ssh_calls() == []


def test_deploy_uploads_a_complete_archive_with_real_tar(tmp_path):
    """Real tar writes the archive; the fake ssh reads it from stdin like the server would."""
    import tarfile

    rec = Recorder()
    received = {}

    def run(cmd, **kwargs):
        if cmd[0] == "tar":
            return subprocess.run(cmd, **kwargs)
        if cmd[0] == "ssh":
            received["names"] = tarfile.open(fileobj=io.BytesIO(kwargs["stdin"].read()), mode="r:gz").getnames()
        return subprocess.CompletedProcess(cmd, 0)

    run_deploy(rec, tmp_path, run=run)
    assert any(name.endswith("index.html") for name in received["names"])


def test_dry_run_builds_but_does_not_connect(tmp_path, capsys):
    rec = Recorder()
    run_deploy(rec, tmp_path, dry_run=True)
    assert len(rec.builds) == 1
    assert rec.ssh_calls() == [] and rec.tar_calls() == []
    assert "ssh deploy@suma.example.hr" in capsys.readouterr().out


def test_cli_deploy_requires_host(monkeypatch):
    monkeypatch.delenv("SUMA_DEPLOY_HOST", raising=False)
    with pytest.raises(SystemExit, match="SUMA_DEPLOY_HOST"):
        cli.main(["deploy"])


def test_cli_deploy_reads_env_defaults(monkeypatch):
    import suma.deploy

    seen = {}
    monkeypatch.setattr(suma.deploy, "deploy", lambda **kw: seen.update(kw) or RELEASE)
    monkeypatch.setenv("SUMA_DEPLOY_HOST", "deploy@env.test")
    monkeypatch.setenv("SUMA_SITE_URL", "https://env.test")
    monkeypatch.delenv("SUMA_DEPLOY_PATH", raising=False)
    cli.main(["deploy"])
    assert seen["host"] == "deploy@env.test"
    assert seen["site_url"] == "https://env.test"
    assert seen["remote_path"] == "/srv/suma"
    assert seen["dry_run"] is False
