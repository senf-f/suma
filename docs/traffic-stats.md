# Traffic stats

Traffic is measured from Caddy's access log with [GoAccess](https://goaccess.io/). There is no
JavaScript, cookie or third-party service on the site, so no consent banner is needed.

Limits:
- Bots are only partly filtered (`--ignore-crawlers`), so counts are an upper bound.
- Visitor IPs are masked before they are written (IPv4 to /24, IPv6 to /48), so "unique visitors"
  is approximate.
- Searches run entirely in the browser (Pagefind), so search terms never reach the log.
- Stats start from 2026-11-19, when logging was switched on.

## Server setup (done once, as root)

### 1. Access log in Caddy

Inside the `suma.oprobate.eu { ... }` block of `/etc/caddy/Caddyfile`:

```caddy
	log {
		output file /var/log/caddy/suma-access.log {
			roll_size 50MiB
			roll_keep 10
			roll_keep_for 2160h
		}
		format filter {
			request>remote_ip ip_mask {
				ipv4 24
				ipv6 48
			}
			request>client_ip ip_mask {
				ipv4 24
				ipv6 48
			}
		}
	}
```

The log rotates at 50 MB and keeps at most 10 compressed old files for up to 90 days.

Validate and reload:

```sh
sudo -u caddy caddy validate --config /etc/caddy/Caddyfile && systemctl reload caddy
```

**Validate as the `caddy` user, not as root.** `caddy validate` opens the log file, so running it as
root creates `suma-access.log` owned by root. The `caddy` service then cannot open it, and the
reload fails with `setting up custom log 'log0': opening log writer ...`. The old config keeps
serving, so the site stays up. Fix:

```sh
chown -R caddy:caddy /var/log/caddy && systemctl reload caddy
```

Check that requests are logged (the IP should end in `.0`):

```sh
curl -sI https://suma.oprobate.eu >/dev/null; tail -n1 /var/log/caddy/suma-access.log
```

### 2. GoAccess

```sh
apt-get install -y goaccess
```

Any version from 1.6 up can read `--log-format=CADDY`. The Ubuntu package is built with
`--enable-geoip=mmdb` (check with `goaccess -V`), which the next step needs.

### 3. Visitor locations (GeoIP)

GoAccess looks up each IP in the free [DB-IP](https://db-ip.com) "IP to City Lite" database
(CC BY 4.0, updated monthly, no account). Masked IPs still look up correctly because the
database maps whole address blocks. GoAccess 1.9 shows only continent and country; the city data
in the file is not displayed. Country lookups are reliable.

```sh
mkdir -p /usr/local/share/GeoIP
curl -fSL "https://download.db-ip.com/free/dbip-city-lite-$(date +%Y-%m).mmdb.gz" -o /tmp/dbip.mmdb.gz && gunzip -c /tmp/dbip.mmdb.gz > /usr/local/share/GeoIP/dbip-city-lite.mmdb && rm /tmp/dbip.mmdb.gz
ls -la /usr/local/share/GeoIP/
```

The file should be roughly 100 MB or more. If GoAccess reports `Unable to open GeoIP2 database`, the
file is missing or empty, so rerun the download.

Refresh it monthly with `/etc/cron.d/dbip-update`. The `%` signs must stay escaped in cron. The job
runs on the 3rd of the month because the new file comes out at the start of each month. It writes
to a temporary file first, so a failed download never replaces the working database:

```cron
0 4 3 * * root curl -fsSL "https://download.db-ip.com/free/dbip-city-lite-$(date +\%Y-\%m).mmdb.gz" | gunzip > /usr/local/share/GeoIP/dbip-city-lite.mmdb.new && mv /usr/local/share/GeoIP/dbip-city-lite.mmdb.new /usr/local/share/GeoIP/dbip-city-lite.mmdb
```

## Reading the stats

The log is readable only by root and `caddy`, so these commands run as root.

Interactive, in the terminal on the VPS (`q` quits):

```sh
zcat -f /var/log/caddy/suma-access.log* | goaccess - --log-format=CADDY --ignore-crawlers --geoip-database=/usr/local/share/GeoIP/dbip-city-lite.mmdb
```

HTML report on Windows (PowerShell). The report is generated on the server, copied down, and never
published:

```powershell
ssh root@suma.oprobate.eu "zcat -f /var/log/caddy/suma-access.log* | goaccess - --log-format=CADDY --ignore-crawlers --geoip-database=/usr/local/share/GeoIP/dbip-city-lite.mmdb -o /tmp/suma.html >/dev/null && cat /tmp/suma.html" > $HOME\suma-stats.html; start $HOME\suma-stats.html
```

Useful panels:
- **Requested Files:** the most-read questions.
- **Referring Sites:** where visitors came from.
- **Not Found URLs:** deep links that people actually followed and that are broken.
- **Geo Location:** visitors by continent and country.
