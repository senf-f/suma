"""Traffic report: GoAccess dashboard plus a per-city table, in one local HTML page.

One ssh call runs everything on the VPS (see docs/traffic-stats.md for the server setup):
GoAccess renders its HTML report from the Caddy access log, then each visitor IP is looked up
in the DB-IP city database, because GoAccess itself only shows countries. Both come back on
stdout, separated by MARKER, and are combined here into one self-contained file.
"""
import html
import shlex
import subprocess
from collections import Counter
from pathlib import Path

MARKER = "@@SUMA-STATS-CITIES@@"
LOGS = "/var/log/caddy/suma-access.log*"
GEOIP_DB = "/usr/local/share/GeoIP/dbip-city-lite.mmdb"

# Page views only: no assets or search index files, no errors, no obvious bots.
_JQ_PAGE_VIEW_IPS = (
    'select((.request.uri | test("^/(static|pagefind)/|^/favicon|^/robots")) | not)'
    " | select(.status < 400)"
    ' | select(((.request.headers["User-Agent"][0] // "")'
    ' | test("bot|crawl|spider|slurp|curl|wget|python|go-http|httpx|scan"; "i")) | not)'
    " | .request.remote_ip"
)


def remote_script() -> str:
    """Shell run on the server. Prints the GoAccess HTML, MARKER, then `count<TAB>country<TAB>city` per IP."""
    return "\n".join([
        "set -eu",
        f"DB={GEOIP_DB}",
        'T=$(mktemp --suffix=.html); trap \'rm -f "$T"\' EXIT',
        f'zcat -f {LOGS} | goaccess - --log-format=CADDY --ignore-crawlers --geoip-database="$DB" -o "$T" >/dev/null',
        'cat "$T"',
        f"echo; echo {MARKER}",
        f"zcat -f {LOGS} | jq -r {shlex.quote(_JQ_PAGE_VIEW_IPS)} | sort | uniq -c | while read -r n ip; do",
        '  cc=$(mmdblookup -f "$DB" -i "$ip" country iso_code 2>/dev/null | grep -o \'"[^"]*"\' | head -n1 | tr -d \'"\')',
        '  city=$(mmdblookup -f "$DB" -i "$ip" city names en 2>/dev/null | grep -o \'"[^"]*"\' | head -n1 | tr -d \'"\')',
        "  printf '%s\\t%s\\t%s\\n' \"$n\" \"$cc\" \"$city\"",
        "done",
    ])


def parse_output(text: str) -> tuple[str, list[tuple[int, str, str]]]:
    """Split the remote output into the GoAccess HTML and page views per (country, city), most first."""
    if MARKER not in text:
        raise SystemExit("unexpected output from the server (no city section); is goaccess installed?")
    report, _, rows = text.partition(MARKER)
    totals: Counter[tuple[str, str]] = Counter()
    for line in rows.splitlines():
        parts = line.split("\t")
        if len(parts) != 3 or not parts[0].strip().isdigit():
            continue
        totals[(parts[1] or "??", parts[2] or "unknown")] += int(parts[0])
    cities = sorted(((n, cc, city) for (cc, city), n in totals.items()), key=lambda r: (-r[0], r[1], r[2]))
    return report.strip(), cities


def render_report(goaccess_html: str, cities: list[tuple[int, str, str]], limit: int = 50) -> str:
    total = sum(n for n, _, _ in cities)
    rows = "\n".join(
        f'<tr><td class="n">{n}</td><td class="n">{n / total:.1%}</td><td>{html.escape(cc)}</td><td>{html.escape(city)}</td></tr>'
        for n, cc, city in cities[:limit]
    )
    shown = f"top {limit} of {len(cities)}" if len(cities) > limit else f"{len(cities)}"
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Suma traffic</title>
<style>
  :root {{ color-scheme: light dark; }}
  body {{ margin: 0; font: 14px system-ui, sans-serif; }}
  details {{ padding: 8px 16px; border-bottom: 1px solid #8884; }}
  summary {{ cursor: pointer; font-weight: 600; }}
  table {{ border-collapse: collapse; margin: 8px 0; }}
  th, td {{ padding: 2px 12px 2px 0; text-align: left; }}
  td.n, th.n {{ text-align: right; font-variant-numeric: tabular-nums; }}
  iframe {{ display: block; width: 100%; height: 100vh; border: 0; }}
</style>
</head>
<body>
<details>
<summary>Cities: {total} page views from {shown} places (bots filtered by user agent, approximate)</summary>
<table>
<tr><th class="n">Views</th><th class="n">Share</th><th>Country</th><th>City</th></tr>
{rows}
</table>
</details>
<iframe title="GoAccess report" srcdoc="{html.escape(goaccess_html, quote=True)}"></iframe>
</body>
</html>
"""


def stats(host: str, out: Path, *, run=subprocess.run) -> Path:
    """Fetch the report from `host` (needs root: the log is not world-readable) and write it to `out`."""
    proc = run(["ssh", host, "sh -c " + shlex.quote(remote_script())], capture_output=True)
    if proc.returncode == 255:
        raise SystemExit(f"ssh could not connect to {host} (check the key with: ssh {host} true)")
    if proc.returncode != 0:
        err = proc.stderr.decode("utf-8", "replace").strip()
        raise SystemExit(f"building the report on {host} failed (exit {proc.returncode}):\n{err}")
    report, cities = parse_output(proc.stdout.decode("utf-8", "replace"))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_report(report, cities), encoding="utf-8")
    return out
