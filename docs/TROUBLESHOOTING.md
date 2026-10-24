# ServiceGuard Troubleshooting Guide

Built from three incidents reproduced during testing. Evidence for each is
in `evidence/` and `logs/incidents.jsonl`.

## Quick triage order

1. What does ServiceGuard report? `python src/serviceguard.py --once`
2. Is the service running? `systemctl status nginx --no-pager`
3. Is anything listening on the port? `sudo ss -tlnp | grep 8080`
4. What does the server answer? `curl -i http://localhost:8080/health`
5. Is the config valid? `sudo nginx -t`
6. What do the logs say? `sudo journalctl -u nginx -n 20 --no-pager` and
   `sudo tail -n 20 /var/log/nginx/testsite_error.log`

## Incident 1: service stopped

- **Symptom:** `connection refused or unreachable` on both checks.
- **Confirm:** `systemctl is-active nginx` prints `inactive`, `ss` shows
  nothing on 8080, `curl` says it could not connect.
- **Cause (test):** `sudo systemctl stop nginx`.
- **Fix:** `sudo nginx -t && sudo systemctl restart nginx`
- **Verify:** `curl -i http://localhost:8080/health` returns `200` and `OK`.
- **ServiceGuard:** recovered automatically on attempt 1 (~6.5s detected
  downtime). Evidence: `evidence/01-stopped-service.log`.

## Incident 2: broken configuration

- **Symptom:** same as Incident 1, but recovery keeps failing.
- **Confirm:** `sudo nginx -t` fails and names the file and line, for
  example `unknown directive "this_is_not_a_directive" in
  /etc/nginx/sites-enabled/testsite:19`.
- **Cause (test):** an invalid line appended to the site config.
- **Fix:** correct or restore the config, run `sudo nginx -t` until it
  passes, then `sudo systemctl start nginx`.
- **ServiceGuard:** refused to restart on both attempts because the config
  test failed, logged `recovery_exhausted`, and waited for a human.
  Evidence: `evidence/02-broken-config.log`.
- **Lesson:** always test the config before restarting. Restarting onto a
  broken config turns a partial outage into a full one.

## Incident 3: service running, endpoint broken

- **Symptom:** `health: unexpected status 404 (expected 200)`. The `home`
  check still passes.
- **Confirm:** `systemctl is-active nginx` prints `active`, but
  `curl -i http://localhost:8080/health` returns 404. Check the file with
  `ls -l /var/www/testsite/`.
- **Cause (test):** the `health` file was moved out of the web root.
- **Fix:** restore the file, for example
  `sudo cp testsite/health /var/www/testsite/health`. No restart needed.
- **ServiceGuard:** both restarts ran successfully but did not help, so it
  escalated. Evidence: `evidence/03-missing-health-file.log`.
- **Lesson:** a service can be "running" and still broken. Check the
  response, not just the process.

## Reading the logs

| Log line | Meaning |
|---|---|
| `Status: DOWN (1/2)` | First failed check, no incident yet |
| `INCIDENT OPENED` | Threshold reached |
| `Recovery attempt n/N` | Config test, restart, `is-active` being run |
| `Recovery commands succeeded` | Commands ran. The service is not yet confirmed healthy |
| `Recovery attempts exhausted` | ServiceGuard gave up. A human is needed |
| `INCIDENT RESOLVED` | A fresh HTTP check passed again |

## Not covered by these tests

Port conflicts, full disks, permission errors, slow responses and
crashing application code were not tested.
