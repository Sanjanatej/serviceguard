#!/usr/bin/env python3
"""Build a Markdown summary table from logs/incidents.jsonl."""
import json
from collections import OrderedDict
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
SRC = BASE / "logs" / "incidents.jsonl"
OUT = BASE / "evidence" / "incident-summary.md"

incidents = OrderedDict()
for line in SRC.read_text().splitlines():
    if not line.strip():
        continue
    e = json.loads(line)
    inc = incidents.setdefault(e["incident_id"], {
        "opened": "", "reason": "", "attempts": 0, "cmd_ok": 0,
        "exhausted": False, "downtime": None})
    ev = e["event"]
    if ev == "incident_opened":
        inc["opened"], inc["reason"] = e["time"], e["reason"]
    elif ev == "recovery_attempt":
        inc["attempts"] += 1
        inc["cmd_ok"] += 1 if e["commands_succeeded"] else 0
    elif ev == "recovery_exhausted":
        inc["exhausted"] = True
    elif ev == "incident_resolved":
        inc["downtime"] = e["downtime_seconds"]

rows = ["| Incident | Opened (UTC) | Reason | Attempts | Commands OK | Resolved by | Detected downtime |",
        "|---|---|---|---|---|---|---|"]
for iid, i in incidents.items():
    by = "manual fix" if i["exhausted"] else "automatic recovery"
    if i["downtime"] is None:
        by, dt = "unresolved", "n/a"
    else:
        dt = f"{i['downtime']}s"
    reason = i["reason"].replace("|", "/")
    rows.append(f"| {iid} | {i['opened']} | {reason} | {i['attempts']} | "
                f"{i['cmd_ok']}/{i['attempts']} | {by} | {dt} |")

OUT.write_text("\n".join(rows) + "\n")
print("\n".join(rows))
