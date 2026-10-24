#!/usr/bin/env python3
"""ServiceGuard v2: per-target monitoring, incident logging, recovery."""
import argparse
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from checker import check_service
from recovery import attempt_recovery
import metrics

BASE_DIR = Path(__file__).resolve().parent.parent
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)
EVENTS_FILE = LOG_DIR / "incidents.jsonl"
log = logging.getLogger("serviceguard")


def setup_logging():
    fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(message)s")
    for h in (logging.FileHandler(LOG_DIR / "serviceguard.log"),
              logging.StreamHandler()):
        h.setFormatter(fmt)
        log.addHandler(h)
    log.setLevel(logging.INFO)


def write_event(event, **fields):
    rec = {"time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "event": event, **fields}
    with open(EVENTS_FILE, "a") as f:
        f.write(json.dumps(rec) + "\n")


def load_config(path):
    cfg = json.loads(Path(path).read_text())
    for key, val in {"interval": 5, "timeout": 3, "threshold": 2,
                     "max_attempts": 3, "verify_wait": 3}.items():
        cfg.setdefault(key, val)
    for t in cfg["targets"]:
        for key in ("name", "url", "service"):
            if key not in t:
                raise SystemExit(f"config error: target missing '{key}': {t}")
        t.setdefault("expected_text", None)
    return cfg


def summary(results):
    return " | ".join(
        f"{t['name']} " + (f"OK {r['latency_ms']}ms" if r["ok"] else "DOWN")
        for t, r in results)


def new_state():
    return {"failures": 0, "first_failure": None, "incident": None,
            "attempts": 0, "exhausted": False}




def process(t, st, cfg, recover):
    """Check one target, update its incident state, recover if enabled."""
    r = check_service(t["url"], 200, t["expected_text"], cfg["timeout"])
    name = t["name"]
    metrics.record_check(name, r["ok"], r["latency_ms"])
    if r["ok"]:
        if st["incident"]:
            down = round(time.monotonic() - st["first_failure"], 1)
            log.info("[%s] INCIDENT RESOLVED %s | downtime ~%ss | attempts: %d",
                     name, st["incident"], down, st["attempts"])
            metrics.incident_resolved(name)
            write_event("incident_resolved", target=name,
                        incident_id=st["incident"], downtime_seconds=down,
                        recovery_attempts=st["attempts"])
        st.update(new_state())
        return r

    st["failures"] += 1
    if st["failures"] == 1:
        st["first_failure"] = time.monotonic()
    if st["incident"]:
        log.warning("[%s] still DOWN | %s", name, r["reason"])
    else:
        log.warning("[%s] DOWN (%d/%d) | %s", name, st["failures"],
                    cfg["threshold"], r["reason"])
        if st["failures"] >= cfg["threshold"]:
            st["incident"] = f"INC-{datetime.now():%Y%m%d-%H%M%S}-{name}"
            log.error("[%s] INCIDENT OPENED %s | %s", name, st["incident"],
                      r["reason"])
            metrics.incident_opened(name)
            write_event("incident_opened", target=name,
                        service=t["service"], incident_id=st["incident"],
                        reason=r["reason"])

    if st["incident"] and recover:
        if st["attempts"] < cfg["max_attempts"]:
            st["attempts"] += 1
            log.warning("[%s] Recovery attempt %d/%d for '%s'", name,
                        st["attempts"], cfg["max_attempts"], t["service"])
            metrics.recovery_attempted(name)
            out = attempt_recovery(t["service"])
            write_event("recovery_attempt", target=name,
                        incident_id=st["incident"], attempt=st["attempts"],
                        commands_succeeded=out["success"], steps=out["steps"])
            log.info("[%s] Recovery commands %s; re-checking next cycle", name,
                     "succeeded" if out["success"] else "FAILED")
            time.sleep(cfg["verify_wait"])
        elif not st["exhausted"]:
            log.error("[%s] Recovery attempts exhausted for %s - manual "
                      "intervention required", name, st["incident"])
            write_event("recovery_exhausted", target=name,
                        incident_id=st["incident"])
            st["exhausted"] = True
    return r


def main():
    p = argparse.ArgumentParser(description="ServiceGuard v2")
    p.add_argument("--config", default=str(BASE_DIR / "config.json"))
    p.add_argument("--once", action="store_true",
                   help="one check of every target; exit 0 if all up, else 1")
    p.add_argument("--recover", action="store_true",
                   help="attempt automatic recovery")
    args = p.parse_args()
    cfg = load_config(args.config)
    setup_logging()

    if args.once:
        res = [(t, check_service(t["url"], 200, t["expected_text"],
                                 cfg["timeout"])) for t in cfg["targets"]]
        bad = [t["name"] for t, r in res if not r["ok"]]
        log.info("%s | %s", "Status: OK" if not bad else "Status: DOWN",
                 summary(res))
        sys.exit(1 if bad else 0)

    metrics.start_server(cfg.get("metrics_port", 9101))
    states = {t["name"]: new_state() for t in cfg["targets"]}
    log.info("ServiceGuard v2 started (targets=%d, interval=%ss, threshold=%d,"
             " recover=%s)", len(cfg["targets"]), cfg["interval"],
             cfg["threshold"], args.recover)
    try:
        while True:
            res = [(t, process(t, states[t["name"]], cfg, args.recover))
                   for t in cfg["targets"]]
            log.info("Cycle | %s", summary(res))
            time.sleep(cfg["interval"])
    except KeyboardInterrupt:
        log.info("ServiceGuard stopped by user")


if __name__ == "__main__":
    main()
