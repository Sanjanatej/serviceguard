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
