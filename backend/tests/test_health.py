"""Tests for `/health` (SPEC §6.3).

Mock mode is the only branch we can exercise without a Postgres. The
DB-ok path needs a real engine; cover that with an integration test once
DB tests are wired up.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


class TestHealthMockMode:
    def test_returns_skipped_db_in_mock_mode(self):
        c = TestClient(app)
        r = c.get("/health")
        assert r.status_code == 200
        body = r.json()
        assert body["db"] == "skipped"
        assert body["eero"] in {"configured", "missing"}
        assert body["last_poll"] is None
        assert "now" in body

    def test_eero_status_reflects_token_presence(self, monkeypatch):
        from app.api import health as health_module

        monkeypatch.setattr(health_module.settings, "EERO_API_TOKEN", "abc")
        c = TestClient(app)
        body = c.get("/health").json()
        assert body["eero"] == "configured"

        monkeypatch.setattr(health_module.settings, "EERO_API_TOKEN", "")
        body = c.get("/health").json()
        assert body["eero"] == "missing"


class TestMetrics:
    def test_metrics_text_format(self):
        c = TestClient(app)
        r = c.get("/metrics")
        assert r.status_code == 200
        ct = r.headers.get("content-type", "")
        assert "text/plain" in ct
        # Standard Prometheus exposition format
        assert "# TYPE wifimon_dashboard_requests_total counter" in r.text

    def test_dashboard_counter_increments(self):
        c = TestClient(app)
        # Read baseline
        baseline = _counter_value(c.get("/metrics").text, 'mode="mock"')
        c.get("/api/v1/dashboard")
        c.get("/api/v1/dashboard")
        after = _counter_value(c.get("/metrics").text, 'mode="mock"')
        assert after - baseline >= 2.0


def _counter_value(text: str, label_match: str) -> float:
    for line in text.splitlines():
        if line.startswith("wifimon_dashboard_requests_total") and label_match in line:
            return float(line.rsplit(" ", 1)[1])
    return 0.0
