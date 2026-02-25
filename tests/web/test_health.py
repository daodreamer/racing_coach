"""Wave 3 — /health endpoint (2 tests)."""

from __future__ import annotations


def test_health_status_200(client):
    resp = client.get("/health")
    assert resp.status_code == 200


def test_health_body(client):
    resp = client.get("/health")
    data = resp.json()
    assert data["status"] == "ok"
    assert data["version"] == "0.1.0"
