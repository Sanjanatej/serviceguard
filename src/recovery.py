"""Controlled recovery: validate (nginx only), restart, confirm."""
import subprocess

ALLOWED = {"nginx", "sg-backend-a", "sg-backend-b"}


def _run(cmd):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return {"cmd": " ".join(cmd), "returncode": p.returncode,
                "output": (p.stdout + p.stderr).strip()[-300:]}
    except subprocess.TimeoutExpired:
        return {"cmd": " ".join(cmd), "returncode": -1,
                "output": "command timed out"}


def attempt_recovery(service):
    if service not in ALLOWED:
        return {"success": False, "steps": [{
            "cmd": "(none)", "returncode": -1,
            "output": f"service {service!r} is not on the allow-list"}]}
    steps = []
    if service == "nginx":
        # Never restart nginx onto a broken config.
        test = _run(["sudo", "-n", "/usr/sbin/nginx", "-t"])
        steps.append(test)
        if test["returncode"] != 0:
            return {"success": False, "steps": steps}
    restart = _run(["sudo", "-n", "/usr/bin/systemctl", "restart", service])
    steps.append(restart)
    active = _run(["systemctl", "is-active", service])
    steps.append(active)
    ok = restart["returncode"] == 0 and active["output"] == "active"
    return {"success": ok, "steps": steps}
