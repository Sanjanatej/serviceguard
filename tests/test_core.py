"""Tests for metrics, config loading and the recovery allow-list."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import metrics  # noqa: E402
import recovery  # noqa: E402
import serviceguard  # noqa: E402


def test_metrics_counters_and_incident_flag():
    metrics.record_check("t1", True, 4.2)
    metrics.incident_opened("t1")
    metrics.recovery_attempted("t1")
    out = metrics.render()
    assert 'serviceguard_target_up{target="t1"} 1' in out
    assert 'serviceguard_incidents_opened_total{target="t1"} 1' in out
    assert 'serviceguard_recovery_attempts_total{target="t1"} 1' in out
    assert 'serviceguard_incident_active{target="t1"} 1' in out
    metrics.incident_resolved("t1")
    assert 'serviceguard_incident_active{target="t1"} 0' in metrics.render()


def test_recovery_refuses_unlisted_service():
    result = recovery.attempt_recovery("sshd")
    assert result["success"] is False
    assert "allow-list" in result["steps"][0]["output"]


def test_load_config_applies_defaults(tmp_path):
    f = tmp_path / "c.json"
    f.write_text('{"targets":[{"name":"a","url":"http://x","service":"nginx"}]}')
    cfg = serviceguard.load_config(f)
    assert cfg["threshold"] == 2
    assert cfg["targets"][0]["expected_text"] is None


def test_load_config_rejects_missing_key(tmp_path):
    f = tmp_path / "c.json"
    f.write_text('{"targets":[{"name":"a","url":"http://x"}]}')
    with pytest.raises(SystemExit):
        serviceguard.load_config(f)
