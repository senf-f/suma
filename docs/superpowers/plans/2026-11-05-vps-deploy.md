# VPS Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Serve the public Croatian reader at `https://suma.example.hr` from a fresh Ubuntu/Debian VPS, deployed with one command from the owner's Windows machine, with suggestion links going to the public GitHub repo `senf-f/suma`.

**Architecture:** The site can only be built where `data/latin/` exists (gitignored, never published), so there is no CI build: `suma deploy` builds a fresh public site locally, streams it over SSH as a tar archive into a new release directory on the VPS, and atomically repoints a `current` symlink. Caddy serves `/srv/suma/current` and obtains the Let's Encrypt certificate itself once the subdomain's A record points at the VPS.

**Tech Stack:** Python 3 + uv (existing `suma` CLI), Windows built-in OpenSSH `ssh` and `tar`, Caddy 2 on Ubuntu 24.04 / Debian 12, DNS at the domain registrar, `gh` CLI, `git-filter-repo` via `uvx`.

**Spec:** No deployment spec. `docs/superpowers/specs/2026-10-25-suma-pilot-design.md` (its Stack row says "GitHub Pages"; this plan replaces that hosting choice and keeps every other rule of the spec).

**Placeholder:** `suma.example.hr` throughout is the subdomain to be chosen; `203.0.113.10` is the VPS IPv4 address. Substitute both when executing. Nothing in committed code hardcodes the hostname except the default in Task 2.

## Global Constraints

- Corpus Thomisticum terms: "translation OK, deep links OK, Latin text must never be published (site, issues, public repo)".
- Spec: the `--with-latin` build is "for the owner's local review only. Such a build is never deployed or shared."
- The public repo must contain no Corpus Thomisticum Latin in any commit, not just in the current tree.
- Owner machine is Windows 11 (PowerShell + Git Bash); use only the built-in `ssh.exe`/`tar.exe`, no rsync.
- All Python runs through `uv run`; tests through `uv run pytest`.
- Server layout: `/srv/suma/releases/<UTC timestamp>/` and symlink `/srv/suma/current`; keep the 5 newest releases.
- Deploy user `deploy` (no sudo); SSH key login only.

## Review Focus

1. Upload interrupted halfway (Wi-Fi drop, Ctrl+C) → the live site keeps serving the previous release; the swap happens only after the archive extracted completely (Task 3, `test_remote_script_swaps_only_after_extract`).
2. Owner has a `dist-la/` or `dist/` lying around from a `--with-latin` review build → deploy never uploads an existing directory; it always builds fresh with `with_latin=False` (Task 3, `test_deploy_builds_fresh_public_site`).
3. SSH fails (key not loaded, host unreachable, wrong user) → command exits non-zero with a readable message and nothing on the server changes (Task 3, `test_deploy_fails_loudly_when_ssh_fails`).
4. Deep link without `.html` or a mistyped page (`/I/q003`, `/I/q999.html`) → `.html` is tried, otherwise a Croatian 404 page with working links, not a bare Caddy error (Task 2 `test_404_page_uses_absolute_links`, Task 6 smoke check).
5. Issue links after the move → "Predloži poboljšanje" bodies cite the page on the new subdomain, not `senf-f.github.io` (Task 2, `test_issue_links_use_site_url`).

---

### Task 1: Scrub Latin from git history and publish the repo

The fixture blob introduced in `1f0d8ce` (`tests/fixtures/sth_sample.html`, real text of I q.2) is still in history; commit `8656786` replaced it with invented text. Rewrite history so every commit carries the invented version, then push. Do this first: it rewrites all commit hashes.

**Files:**
- Create: `scripts/scan_history_latin.py`

**Interfaces:**
- Produces: `uv run python scripts/scan_history_latin.py` → prints `path [(blob, hits)]` per suspicious blob in all of history, exits 1 if any, 0 and prints `clean` otherwise. Run it before every push.

- [ ] **Step 1: Write `scripts/scan_history_latin.py`.** For every blob in `git rev-list --all --objects` outside `data/hr/`, flag lines with ≥ 6 matches of `\b(quod|est|sed|enim|autem|ergo|dicendum|videtur|sicut|igitur|non|esse|unde|quia)\b` (case-insensitive), skipping lines containing `fictus`.
- [ ] **Step 2: Run it.** Expected: exactly one hit, `tests/fixtures/sth_sample.html` with blob `adb2951…`, exit 1.
- [ ] **Step 3: Back up locally** (the backup contains Latin and is never pushed anywhere): `git clone --mirror . ../suma-backup-before-scrub.git`
- [ ] **Step 4: Rewrite the blob.** Copy the current fixture to the scratch location, then:
  ```bash
  FULL=$(git rev-list --all --objects | grep sth_sample.html | awk '{print $1}' | grep '^adb2951')
  cp tests/fixtures/sth_sample.html ../sth_sample_fictus.html
  uvx git-filter-repo --force --blob-callback "
  import pathlib
  if blob.original_id == b'$FULL':
      blob.data = pathlib.Path('../sth_sample_fictus.html').read_bytes()
  "
  ```
- [ ] **Step 5: Verify.** `uv run python scripts/scan_history_latin.py` → `clean`, exit 0. `git cat-file -e $FULL` → fails. `uv run pytest -q` → all pass. `git log --oneline | wc -l` unchanged from before the rewrite.
- [ ] **Step 6: Commit the script.** `git add scripts/scan_history_latin.py && git commit -m "chore: history scan for Corpus Thomisticum Latin before pushing"`
- [ ] **Step 7: Publish (owner runs, needs `gh auth login`).** `gh repo create senf-f/suma --public --source . --remote origin --description "Hrvatski prijevod Sume teologije"` then `uv run python scripts/scan_history_latin.py && git push -u origin master`. Verify: `gh repo view senf-f/suma --json hasIssuesEnabled` → `true`.

### Task 2: Configurable site URL and a 404 page

**Files:**
- Modify: `src/suma/reader.py` (`build`)
- Modify: `src/suma/cli.py` (`cmd_build`, `build` subparser)
- Create: `src/suma/reader_templates/404.html`
- Test: `tests/test_reader.py`, `tests/test_cli.py`

**Interfaces:**
- Consumes: existing `build(latin_dir, hr_dir, glossary_path, out_dir, repo="senf-f/suma", site_url=..., with_latin=False)`.
- Produces: `DEFAULT_SITE_URL = "https://suma.example.hr"` in `suma/reader.py` (replacing the `senf-f.github.io/suma` default); `build` also writes `out_dir/404.html`; CLI `suma build --site-url URL` (default: env `SUMA_SITE_URL`, else `DEFAULT_SITE_URL`). Task 3 calls `build(..., site_url=..., with_latin=False)`.

- [ ] **Step 1: Write failing tests** in `tests/test_reader.py`:
  ```python
  def test_issue_links_use_site_url(latin_q2, tmp_path):
      hr = tmp_path / "hr"
      write_units(OPUS, "I", 2, {"I.q2.a3.ad1": "Na prvo"}, "1", 1, hr)
      build(latin_q2, hr, tmp_path / "none.yaml", tmp_path / "out", site_url="https://suma.example.hr")
      html = unquote((tmp_path / "out" / "I" / "q002.html").read_text(encoding="utf-8"))
      assert "https://suma.example.hr/I/q002.html" in html
      assert "github.io" not in html

  def test_404_page_uses_absolute_links(site):
      html = (site / "404.html").read_text(encoding="utf-8")
      assert "Stranica nije pronađena" in html
      assert 'href="/index.html"' in html and 'href="/static/style.css"' in html
  ```
  and in `tests/test_cli.py` a test that `suma build --site-url https://x.test` passes `site_url="https://x.test"` to `build` (patch `suma.reader.build` and the pagefind `subprocess.run`, following the existing CLI tests' style).
- [ ] **Step 2: Run** `uv run pytest tests/test_reader.py tests/test_cli.py -q` → the three new tests fail.
- [ ] **Step 3: Implement.** `404.html` extends `base.html`, heading "Stranica nije pronađena", one line "Ova stranica ne postoji ili je premještena." and links to `Sadržaj` and `Glosar`; render it with `root="/"` because it is served at arbitrary paths. Add `--site-url` to the `build` subparser and pass it through.
- [ ] **Step 4: Run** `uv run pytest -q` → all pass.
- [ ] **Step 5: Commit** `git commit -am "feat: configurable site URL and 404 page for self-hosting"` (add the new template file first).

### Task 3: `suma deploy`

**Files:**
- Create: `src/suma/deploy.py`
- Modify: `src/suma/cli.py` (new `deploy` subparser)
- Test: `tests/test_deploy.py`

**Interfaces:**
- Consumes: `build(...)` and `DEFAULT_SITE_URL` from Task 2; pagefind invocation as in `cmd_build` (`[sys.executable, "-m", "pagefind", "--site", str(out)]`).
- Produces:
  - `remote_script(remote_path: str, release: str, keep: int = 5) -> str`: the shell run on the server, reading the tar stream on stdin.
  - `deploy(host: str, remote_path: str, site_url: str, data_dir: Path, *, build_fn=build, run=subprocess.run, popen=subprocess.Popen, now=datetime.now) -> str`: returns the release name; raises `SystemExit` with a message on any failure.
  - CLI: `suma deploy [--host H] [--path P] [--site-url U] [--dry-run]`, defaults from env `SUMA_DEPLOY_HOST` (e.g. `deploy@suma.example.hr`), `SUMA_DEPLOY_PATH` (default `/srv/suma`), `SUMA_SITE_URL`. `--dry-run` builds and prints the ssh command and remote script without connecting.

- [ ] **Step 1: Write failing tests** in `tests/test_deploy.py` (fakes for `build_fn`, `run`, `popen`; no network):
  - `test_remote_script_swaps_only_after_extract`: script starts with `set -eu`; `tar -xzf - -C "$R.partial"` comes before `mv "$R.partial" "$R"`, which comes before `ln -sfn` + `mv -T … /srv/suma/current`, with `R=/srv/suma/releases/20261105T120000Z`.
  - `test_remote_script_keeps_five_releases`: contains `tail -n +6` on the releases listing sorted newest first.
  - `test_deploy_builds_fresh_public_site`: `build_fn` is called once with `with_latin=False`, the given `site_url`, and an `out_dir` that did not exist before the call (a new temp dir, never `dist`/`dist-la`).
  - `test_deploy_rejects_non_https_site_url`: `site_url="http://suma.example.hr"` → `SystemExit` before `build_fn` is called.
  - `test_deploy_fails_loudly_when_ssh_fails`: fake ssh process exits 255 → `SystemExit` whose message contains `ssh` and the host; the release name is not reported as deployed.
  - `test_release_name_is_utc_timestamp`: `now` fixed at 2026-11-05 12:00:00 UTC → release `20261105T120000Z`.
- [ ] **Step 2: Run** `uv run pytest tests/test_deploy.py -q` → all fail (module missing).
- [ ] **Step 3: Implement `src/suma/deploy.py`.** Build into `tempfile.mkdtemp()`, run pagefind, then pipe `tar -czf - -C <out> .` (stdout) into the stdin of `ssh <host> "sh -c " + shlex.quote(remote_script(...))`; stdin carries the archive, so the script travels as the remote command. Check both process return codes; remove the temp dir in `finally`. The remote script, in order: `set -eu`; `R=<path>/releases/<release>`; `mkdir -p "$R.partial"`; `tar -xzf - -C "$R.partial"`; `mv "$R.partial" "$R"`; `ln -sfn "$R" <path>/current.tmp && mv -T <path>/current.tmp <path>/current`; prune with `ls -1dt <path>/releases/*/ | tail -n +6 | xargs -r rm -rf`; `echo deployed <release>`.
- [ ] **Step 4: Wire the CLI** and run `uv run pytest -q` → all pass. Then `uv run suma deploy --host deploy@suma.example.hr --dry-run` prints the command and script and exits 0.
- [ ] **Step 5: Commit** `git add src/suma/deploy.py tests/test_deploy.py src/suma/cli.py && git commit -m "feat: suma deploy - fresh public build streamed to VPS with atomic release swap"`

### Task 4: Server configuration files and runbook

**Files:**
- Create: `deploy/Caddyfile`, `deploy/provision.sh`, `docs/deploy.md`

**Interfaces:**
- Consumes: server layout from Global Constraints; `suma deploy` from Task 3.
- Produces: `provision.sh <hostname> <path-to-owner-pubkey>`, run once as root on the VPS; `docs/deploy.md` is the runbook Tasks 5–6 follow.

- [ ] **Step 1: Write `deploy/Caddyfile`** with the literal placeholder `SUMA_HOST` (provision replaces it):
  ```caddy
  SUMA_HOST {
      root * /srv/suma/current
      encode zstd gzip
      try_files {path} {path}.html
      file_server
      header {
          Strict-Transport-Security "max-age=31536000"
          X-Content-Type-Options "nosniff"
          Referrer-Policy "strict-origin-when-cross-origin"
          -Server
      }
      @assets path /static/* /pagefind/*
      @pages not path /static/* /pagefind/*
      header @assets Cache-Control "public, max-age=3600"
      header @pages Cache-Control "no-cache"
      handle_errors {
          rewrite * /404.html
          file_server
      }
  }
  www.SUMA_HOST {
      redir https://SUMA_HOST{uri} permanent
  }
  ```
  (Asset names are not content-hashed, hence the short max-age. Leave out the `www.` block unless a `www.suma` record is created in Task 5.)
- [ ] **Step 2: Write `deploy/provision.sh`** (`set -euo pipefail`, refuses to run unless root and given 2 args), idempotent so it can be rerun:
  1. `apt-get update && apt-get -y upgrade && apt-get -y install unattended-upgrades ufw debian-keyring debian-archive-keyring apt-transport-https curl`
  2. user `deploy` (`adduser --disabled-password --gecos ""`), `~deploy/.ssh/authorized_keys` from arg 2, mode 600/700
  3. `ufw allow OpenSSH && ufw allow 80/tcp && ufw allow 443/tcp && ufw allow 443/udp && ufw --force enable`
  4. Caddy from the official repo (`https://dl.cloudsmith.io/public/caddy/stable/gpg.key` → `/usr/share/keyrings/caddy-stable-archive-keyring.gpg`, `debian.deb.txt` → `/etc/apt/sources.list.d/caddy-stable.list`, `apt-get install caddy`)
  5. `/srv/suma/releases/` owned by `deploy:deploy`; if `/srv/suma/current` is missing, create release `0-placeholder` with an `index.html` saying "Uskoro." and point `current` at it
  6. `sed "s/SUMA_HOST/$1/g" Caddyfile > /etc/caddy/Caddyfile && caddy validate --config /etc/caddy/Caddyfile && systemctl reload caddy`
  SSH hardening is deliberately not in the script (see Task 5 Step 5) so a typo cannot lock the owner out.
- [ ] **Step 3: Verify syntax locally.** `bash -n deploy/provision.sh` → no output. If Docker is available: `docker run --rm -v "$PWD/deploy:/d" caddy:2 caddy validate --config /d/Caddyfile --adapter caddyfile` after `sed` to a test host → `Valid configuration`.
- [ ] **Step 4: Write `docs/deploy.md`** with these sections: one-time setup (DNS, provision, env vars), routine deploy (`uv run suma deploy`), rollback (`ssh deploy@HOST 'ls -1dt /srv/suma/releases/*/'` then `ln -sfn <older> /srv/suma/current.tmp && mv -T /srv/suma/current.tmp /srv/suma/current`), logs (`journalctl -u caddy -n 100`), certificates (automatic renewal by Caddy, no cron), and the rule "never deploy `dist-la`; `suma deploy` always builds fresh".
- [ ] **Step 5: Commit** `git add deploy docs/deploy.md && git commit -m "feat: Caddy config, VPS provisioning script and deploy runbook"`

### Task 5: Subdomain DNS and VPS provisioning (owner, at the registrar and on the VPS)

No code. Each step has a check that must pass before the next step.

- [ ] **Step 1: Find the VPS addresses.** On the VPS: `curl -4 -s https://ifconfig.co` (IPv4) and `curl -6 -s https://ifconfig.co` (IPv6; if this fails, IPv6 is not working, so don't create an AAAA record).
- [ ] **Step 2: Create the subdomain record at the registrar's DNS panel** for the domain `example.hr`:
  - Type `A`, Name/Host `suma` (only the label; most panels append the domain, a few want `suma.example.hr.` with a trailing dot), Value `203.0.113.10`, TTL 300 (or the panel's minimum).
  - Type `AAAA`, Name `suma`, Value the IPv6 address, only if Step 1 showed working IPv6. A wrong AAAA record breaks certificate issuance for clients that prefer IPv6.
  - Before saving: make sure no other record already exists for `suma` (an old CNAME conflicts with A). If the domain has `CAA` records, add `0 issue "letsencrypt.org"`.
  - Optional `www.suma` record only if the Caddyfile keeps the `www.` block.
- [ ] **Step 3: Verify DNS** from Windows: `nslookup suma.example.hr 1.1.1.1` and `nslookup suma.example.hr 8.8.8.8` → both answer `203.0.113.10`. Propagation for a new name usually takes minutes; wait until both resolvers agree before Step 4 so Caddy's first certificate request succeeds.
- [ ] **Step 4: Provision.** From the repo root on Windows: `scp deploy/Caddyfile deploy/provision.sh $HOME/.ssh/id_ed25519.pub root@203.0.113.10:/root/` then `ssh root@203.0.113.10 "cd /root && bash provision.sh suma.example.hr /root/id_ed25519.pub"` → ends with `Valid configuration`. Check: `curl -sI https://suma.example.hr` from Windows → `HTTP/2 200`, and the browser shows "Uskoro." with a valid Let's Encrypt certificate. If the certificate fails, `ssh root@… journalctl -u caddy -n 50` shows the ACME error (usually DNS not yet propagated or port 80 blocked by the provider's firewall panel).
- [ ] **Step 5: Harden SSH, only after `ssh deploy@suma.example.hr true` succeeds** in a second terminal: on the VPS set `PasswordAuthentication no` and `PermitRootLogin prohibit-password` in `/etc/ssh/sshd_config.d/99-suma.conf`, then `sshd -t && systemctl reload ssh`. Keep the existing session open until a new login works.
- [ ] **Step 6: Set local env vars** (PowerShell, persistent): `setx SUMA_DEPLOY_HOST deploy@suma.example.hr` and `setx SUMA_SITE_URL https://suma.example.hr`; open a new terminal.

### Task 6: First deploy and smoke check

- [ ] **Step 1: Deploy.** `uv run suma deploy` → ends with `deployed 2026…Z`.
- [ ] **Step 2: Smoke check** from Windows:
  - `curl -sI https://suma.example.hr/` → `200`; `curl -sI http://suma.example.hr/` → `308` to `https://`
  - `curl -s https://suma.example.hr/I/q003.html | findstr "Pitanje"` and `curl -sI https://suma.example.hr/I/q003` → `200` (the `try_files` rule)
  - `curl -sI https://suma.example.hr/I/q999.html` → `404`, and the body is the Croatian 404 page
  - `https://suma.example.hr/glosar.html` shows the glossary; the search box returns results for "bitak" (Pagefind loads from `/pagefind/`)
  - A "Predloži poboljšanje" link opens a pre-filled issue on `github.com/senf-f/suma` whose body cites `https://suma.example.hr/…`
- [ ] **Step 3: Latin check against the live site** (local only; prints nothing but a count): a short `uv run python` snippet takes the first 60 characters of 20 random Latin units from `data/latin/I/`, fetches each unit's live page, and asserts none occurs. Expected `0 of 20 found`.
- [ ] **Step 4: Rollback drill.** Deploy a second time, then roll back to the first release with the `docs/deploy.md` command, confirm the site still serves, and roll forward again.
- [ ] **Step 5: Commit** any runbook corrections found during the drill: `git commit -am "docs: deploy runbook fixes from first deploy"` and `git push`.
