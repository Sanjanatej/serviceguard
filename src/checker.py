"""HTTP health check: verifies status code AND page content."""
import time
import requests


def check_service(url, expected_status=200, expected_text=None, timeout=3.0):
    result = {"url": url, "ok": False, "status_code": None,
              "latency_ms": None, "reason": None}
    start = time.monotonic()
    try:
        resp = requests.get(url, timeout=timeout)
        result["status_code"] = resp.status_code
        result["latency_ms"] = round((time.monotonic() - start) * 1000, 1)
        if resp.status_code != expected_status:
            result["reason"] = (f"unexpected status {resp.status_code} "
                                f"(expected {expected_status})")
        elif expected_text and expected_text not in resp.text:
            result["reason"] = f"expected text not found: {expected_text!r}"
        else:
            result["ok"] = True
    except requests.exceptions.ConnectionError:
        result["reason"] = "connection refused or unreachable"
    except requests.exceptions.Timeout:
        result["reason"] = f"timeout after {timeout}s"
    except requests.exceptions.RequestException as exc:
        result["reason"] = f"request error: {type(exc).__name__}"
    return result
