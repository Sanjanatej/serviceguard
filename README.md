# ServiceGuard

A small Python tool that monitors a local web service, detects failures,
logs incidents, and attempts a controlled recovery. It was built and tested
on Ubuntu 24.04 under WSL 2 as a hands-on project covering Linux, Python,
HTTP checks, systemd, logging, and incident handling.

## What it does

1. **Checks** two URLs on a local Nginx test site (`/health` and `/`),
   verifying both the HTTP status code and the page content.
2. **Detects** failure after a configurable number of consecutive failed
   checks (default 2), to avoid reacting to a single blip.
3. **Logs** every incident as a structured JSON event (`logs/incidents.jsonl`)
   and as human-readable lines (`logs/serviceguard.log`).
4. **Recovers** (optional, `--recover`): runs `nginx -t` first, restarts the
   service only if the config is valid, and confirms with `systemctl is-active`.
5. **Verifies** recovery by re-checking over HTTP. A successful restart command
   is not treated as a successful recovery.
6. **Escalates** after a maximum number of attempts and logs that manual
   intervention is required.

## Architecture

```text
Windows 11 -> WSL 2 (Ubuntu 24.04)
                |
                +-- ServiceGuard (Python)
                |     checker.py       HTTP status + content checks
                |     recovery.py      nginx -t -> restart -> is-active
                |     serviceguard.py  monitor loop, incident tracking, logging
                |
                +-- Nginx test site (port 8080, managed by systemd)
                      /health  -> "OK"
                      /        -> "ServiceGuard Test Site"
```

## Project layout

```text
src/        checker.py, recovery.py, serviceguard.py
tests/      unit tests for the checker (pytest)
scripts/    summarize_incidents.py (builds a table from incidents.jsonl)
testsite/   test site files, Nginx config, example sudoers rule
evidence/   raw logs from each failure test + generated summary table
docs/       TEST_RESULTS.md
logs/       incidents.jsonl (tracked as evidence); *.log files are ignored
```

## Setup (Ubuntu 24.04 / WSL 2 with systemd enabled)

```bash
sudo apt update
sudo apt install -y python3-pip python3-venv nginx curl

git clone <your-repo-url> serviceguard && cd serviceguard
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Test site
sudo mkdir -p /var/www/testsite
sudo cp testsite/index.html testsite/health /var/www/testsite/
sudo cp testsite/nginx-testsite.conf /etc/nginx/sites-available/testsite
sudo ln -sf /etc/nginx/sites-available/testsite /etc/nginx/sites-enabled/testsite
sudo nginx -t && sudo systemctl reload nginx

# Least-privilege rule for recovery (replace the username first)
sudo cp testsite/sudoers-serviceguard.example /etc/sudoers.d/serviceguard
sudo chmod 440 /etc/sudoers.d/serviceguard
sudo visudo -cf /etc/sudoers.d/serviceguard
```

The example sudoers file uses the username from the original machine. Edit it
to match yours before installing. The rule allows only two commands:
`systemctl restart nginx` and `nginx -t`.

## Usage

```bash
python src/serviceguard.py --once                # one check, exit 0 (up) or 1 (down)
python src/serviceguard.py --interval 3          # monitor only
python src/serviceguard.py --interval 3 --recover --max-attempts 3
python -m pytest tests/ -v                       # unit tests
python scripts/summarize_incidents.py            # regenerate evidence/incident-summary.md
```

## Test results

Three failure scenarios were run on a local setup. Full details are in
[docs/TEST_RESULTS.md](docs/TEST_RESULTS.md).

| Scenario | Result |
|---|---|
| Nginx stopped | Detected, restarted automatically, verified (~6.5s detected downtime) |
| Broken Nginx config | Recovery refused to restart onto a bad config, escalated, fixed manually |
| `/health` file missing | Restart succeeded but did not fix it, escalated, fixed manually |

Downtime is measured from the first failed check, not the exact moment of
failure. Only the first scenario is automated recovery time. The other two
include the time a human took to fix the problem.

## Design decisions

- **Consecutive-failure threshold** avoids opening incidents on a single failed check.
- **Config test before restart** prevents restarting onto a broken config.
- **Recovery is verified over HTTP**, because a restart command can succeed
  while the service is still unhealthy.
- **Attempt limit with escalation** prevents endless restart loops.
- **Least-privilege sudo** grants only the two commands recovery needs.

## Limitations

- Single machine, single service, one run per scenario. These are
  demonstrations, not statistics.
- Not a cloud deployment and not a replacement for tools like Prometheus or
  Nagios. There is no alerting, dashboard, or metrics storage.
- The consecutive-failure counter keeps counting after the threshold, so logs
  show lines like `DOWN (5/2)`. This is cosmetic.
- The check list and service name are set in `src/serviceguard.py`, not in a
  config file.
- ServiceGuard is not installed as a systemd service; it is run manually.
