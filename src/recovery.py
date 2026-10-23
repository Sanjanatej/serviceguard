"""Controlled recovery: test config first, then restart, then confirm."""
import subprocess


def _run(cmd):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return {"cmd": " ".join(cmd), "returncode": p.returncode,
                "output": (p.stdout + p.stderr).strip()[-300:]}
    except subprocess.TimeoutExpired:
        return {"cmd": " ".join(cmd), "returncode": -1,
                "output": "command timed out"}


def attempt_recovery(service="nginx"):
    steps = []

    # Step 1: never restart onto a broken config.
    config_test = _run(["sudo", "-n", "/usr/sbin/nginx", "-t"])
    steps.append(config_test)
    if config_test["returncode"] != 0:
        return {"success": False, "steps": steps}

    # Step 2: restart the service.
    restart = _run(["sudo", "-n", "/usr/bin/systemctl", "restart", service])
    steps.append(restart)

    # Step 3: ask systemd whether it is actually running.
    active = _run(["systemctl", "is-active", service])
    steps.append(active)

    ok = restart["returncode"] == 0 and active["output"] == "active"
    return {"success": ok, "steps": steps}
