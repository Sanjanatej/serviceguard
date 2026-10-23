#!/usr/bin/env python3
"""ServiceGuard: monitor a local web service, log incidents, attempt recovery."""
import argparse
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from checker import check_service
from recovery import attempt_recovery

BASE_DIR = Path(__file__).resolve().parent.parent
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)
EVENTS_FILE = LOG_DIR / "incidents.jsonl"

SERVICE_NAME = "nginx"
CHECKS = [
    ("health", "http://localhost:8080/health", "OK"),
    ("home", "http://localhost:8080/", "ServiceGuard Test Site"),
]

log = logging.getLogger("serviceguard")


def setup_logging():
    fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(message)s")
    file_handler = logging.FileHandler(LOG_DIR / "serviceguard.log")
    file_handler.setFormatter(fmt)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(fmt)
    log.setLevel(logging.INFO)
    log.addHandler(file_handler)
    log.addHandler(stream_handler)


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def write_event(event, **fields):
    record = {"time": now_iso(), "event": event, **fields}
    with open(EVENTS_FILE, "a") as f:
        f.write(json.dumps(record) + "\n")


def run_checks(timeout):
    results = []
    for name, url, text in CHECKS:
        r = check_service(url, 200, text, timeout)
        r["name"] = name
        results.append(r)
    return all(r["ok"] for r in results), results


def ok_summary(results):
    return " | ".join(f"{r['name']} {r['status_code']} {r['latency_ms']}ms"
                      for r in results)


def fail_summary(results):
    return "; ".join(f"{r['name']}: {r['reason']}"
                     for r in results if not r["ok"])


def main():
    p = argparse.ArgumentParser(description="ServiceGuard monitor")
    p.add_argument("--once", action="store_true",
                   help="run one check, print result, exit 0 (up) or 1 (down)")
    p.add_argument("--interval", type=float, default=5, help="seconds between checks")
    p.add_argument("--timeout", type=float, default=3, help="HTTP timeout in seconds")
    p.add_argument("--threshold", type=int, default=2,
                   help="consecutive failures before opening an incident")
    p.add_argument("--recover", action="store_true", help="attempt automatic recovery")
    p.add_argument("--max-attempts", type=int, default=3)
    p.add_argument("--verify-wait", type=float, default=3,
                   help="seconds to wait after a recovery attempt before re-checking")
    args = p.parse_args()

    setup_logging()

    if args.once:
        ok, results = run_checks(args.timeout)
        if ok:
            log.info("Status: OK | %s", ok_summary(results))
        else:
            log.warning("Status: DOWN | %s", fail_summary(results))
        sys.exit(0 if ok else 1)

    log.info("ServiceGuard started (interval=%ss, threshold=%d, recover=%s)",
             args.interval, args.threshold, args.recover)

    failures = 0
    first_failure = None
    incident = None
    attempts = 0
    exhausted_logged = False

    try:
        while True:
            ok, results = run_checks(args.timeout)

            if ok:
                log.info("Status: OK | %s", ok_summary(results))
                if incident:
                    downtime = round(time.monotonic() - first_failure, 1)
                    log.info("INCIDENT RESOLVED %s | downtime ~%ss | recovery attempts: %d",
                             incident["id"], downtime, attempts)
                    write_event("incident_resolved", incident_id=incident["id"],
                                downtime_seconds=downtime, recovery_attempts=attempts)
                    incident = None
                    attempts = 0
                    exhausted_logged = False
                failures = 0
                first_failure = None
            else:
                failures += 1
                if failures == 1:
                    first_failure = time.monotonic()
                reason = fail_summary(results)
                log.warning("Status: DOWN (%d/%d) | %s",
                            failures, args.threshold, reason)

                if failures >= args.threshold:
                    if incident is None:
                        incident = {"id": datetime.now().strftime("INC-%Y%m%d-%H%M%S")}
                        log.error("INCIDENT OPENED %s | %s", incident["id"], reason)
                        write_event("incident_opened",
                                    incident_id=incident["id"], reason=reason)

                    if args.recover and attempts < args.max_attempts:
                        attempts += 1
                        log.warning("Recovery attempt %d/%d for '%s'",
                                    attempts, args.max_attempts, "nginx")
                        outcome = attempt_recovery(SERVICE_NAME)
                        write_event("recovery_attempt",
                                    incident_id=incident["id"], attempt=attempts,
                                    commands_succeeded=outcome["success"],
                                    steps=outcome["steps"])
                        log.info("Recovery commands %s; re-checking in %ss",
                                 "succeeded" if outcome["success"] else "FAILED",
                                 args.verify_wait)
                        time.sleep(args.verify_wait)
                        continue  # verify immediately

                    if args.recover and not exhausted_logged:
                        log.error("Recovery attempts exhausted for %s - manual "
                                  "intervention required", incident["id"])
                        write_event("recovery_exhausted", incident_id=incident["id"])
                        exhausted_logged = True

            time.sleep(args.interval)
    except KeyboardInterrupt:
        log.info("ServiceGuard stopped by user")


if __name__ == "__main__":
    main()
