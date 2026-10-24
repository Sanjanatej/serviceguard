# ServiceGuard Test Results

Ubuntu 24.04 (WSL 2). Every scenario was run once. Raw logs are in
`evidence/`, and incident events are in `logs/incidents.jsonl`.

## v1: single Nginx site

| Test | Failure | Behavior | Outcome |
|---|---|---|---|
| A | `systemctl stop nginx` | Config test passed, restart worked | Automatic, ~6.5s detected downtime |
| B | Invalid directive in site config | `nginx -t` failed twice, restart never ran | Escalated, fixed manually (~45.5s incl. human time) |
| C | `/health` file removed | Restart succeeded but did not help | Escalated, fixed manually (~25.6s incl. human time) |

Evidence: `evidence/00` to `03`. Test C only applied to the old static site.

## v2: load balancer, two backends

| Test | Failure | Behavior | Outcome |
|---|---|---|---|
| Failover | `systemctl stop sg-backend-b` | 10 of 10 requests returned 200, all from backend a | No user-visible outage |
| Blind spot | Same, with ServiceGuard v1 | `--once` reported OK while a backend was dead | Motivated per-backend checks |
| D | Backend b stopped, v2 running | Incident named `backend-b`, only that service restarted | Automatic, ~9.2s detected downtime |
| Service | Backend b stopped, ServiceGuard under systemd | Same incident flow with no terminal open | Automatic, ~9.1s |
| Service | `SIGKILL` on ServiceGuard | systemd restarted it (`NRestarts=1`) | Monitor restored |

Evidence: `evidence/04`, `05` and `06`.

## Monitoring

- Prometheus scraped ServiceGuard (5s), Node Exporter and itself, and all
  three targets showed `up`.
- A Grafana dashboard showed `backend-b` going DOWN briefly, with one incident
  and one recovery attempt counted.
- Node Exporter metrics were shown with a community dashboard (ID 1860).

## Unit tests

8 pytest tests pass: HTTP checks (success, wrong status, missing text,
connection refused), the recovery allow-list, config loading and the metrics
output. They run in GitHub Actions on every push.

## How to read the numbers

- Downtime is measured from the first failed check, so it is detected downtime.
- Only the ~6.5s, ~9.2s and ~9.1s figures are automated recovery.
- The 45.5s and 25.6s figures include human fix time.

## Not covered

Restart after a full WSL shutdown, both backends failing at once, port
conflicts, full disks, slow responses, alerting and multi-node setups.
