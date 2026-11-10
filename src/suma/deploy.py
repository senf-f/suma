"""Deploy the public reader to the VPS.

The site can only be built here, where data/latin/ exists (it is never published), so
deploy always builds a fresh public site (never the --with-latin review build), streams it
over SSH as a tar archive into a new release directory, and only after it has extracted
completely repoints the `current` symlink that Caddy serves.
"""
import shlex
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from suma.reader import build

KEEP_RELEASES = 5


def release_name(now: datetime) -> str:
    return now.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def remote_script(remote_path: str, release: str, keep: int = KEEP_RELEASES) -> str:
    """Shell run on the server; the release archive arrives on stdin."""
    p = remote_path.rstrip("/")
    return "\n".join([
        "set -eu",
        f"R={p}/releases/{release}",
        f"rm -rf {p}/releases/*.partial",  # leftovers of interrupted deploys
        'mkdir -p "$R.partial"',
        'tar -xzf - -C "$R.partial"',
        'mv "$R.partial" "$R"',
        f'ln -sfn "$R" {p}/current.tmp',
        f"mv -T {p}/current.tmp {p}/current",
        # Release names are UTC timestamps, so name order is age order ("0-placeholder" sorts oldest).
        # Not `ls -t`: tar restores the archive's old mtime onto each release directory.
        f"ls -1d {p}/releases/*/ | sort -r | tail -n +{keep + 1} | xargs -r rm -rf",
        f"echo deployed {release}",
    ])


def deploy(
    host: str,
    remote_path: str,
    site_url: str,
    data_dir: Path,
    *,
    dry_run: bool = False,
    build_fn=build,
    run=subprocess.run,
    popen=subprocess.Popen,
    now=lambda: datetime.now(timezone.utc),
) -> str:
    """Build, upload and activate a release; returns its name. Raises SystemExit on any failure."""
    url = urlsplit(site_url)
    if url.scheme != "https" or not url.netloc:
        raise SystemExit(f"site URL must be https://…, got {site_url!r}")
    release = release_name(now())
    tmp = Path(tempfile.mkdtemp(prefix="suma-deploy-"))
    try:
        out = tmp / "site"
        build_fn(data_dir / "latin", data_dir / "hr", data_dir / "glossary.yaml", out, site_url=site_url, with_latin=False)
        if run([sys.executable, "-m", "pagefind", "--site", str(out)]).returncode != 0:
            raise SystemExit("pagefind indexing failed; nothing was uploaded")
        ssh_cmd = ["ssh", host, "sh -c " + shlex.quote(remote_script(remote_path, release))]
        if dry_run:
            print(f"built {out} (release {release}); would run:\n  tar -czf - -C {out} . | {shlex.join(ssh_cmd)}")
            return release
        tar = popen(["tar", "-czf", "-", "-C", str(out), "."], stdout=subprocess.PIPE)
        ssh = run(ssh_cmd, stdin=tar.stdout)
        tar.stdout.close()
        if tar.wait() != 0:
            raise SystemExit("local tar failed; the server kept the previous release")
        if ssh.returncode != 0:
            raise SystemExit(
                f"ssh to {host} failed (exit {ssh.returncode}); nothing changed on the server "
                "(check the key with: ssh " + host + " true)"
            )
        return release
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
