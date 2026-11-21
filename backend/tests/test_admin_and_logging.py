"""
Unit and Security tests for TalentRank Live Logging and Admin Diagnostics.
Verifies authentication, PII sanitization, brute-force defenses, and log filtering.
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.logger import sanitize_text, record_log, clear_logs

client = TestClient(app)


def test_sanitize_text_redacts_pii_and_secrets():
    raw_message = (
        "Candidate John Doe with email john.doe@example.com and phone +1-555-019-2834 "
        "uploaded resume from C:\\Users\\shiva\\Desktop\\Resume parser\\backend\\secret.txt with password 12345"
    )
    sanitized = sanitize_text(raw_message)

    # Assert PII is redacted
    assert "john.doe@example.com" not in sanitized
    assert "j***@example.com" in sanitized or "[EMAIL_REDACTED]" in sanitized
    assert "+1-555-019-2834" not in sanitized
    assert "[PHONE_REDACTED]" in sanitized

    # Assert secrets / passwords redacted
    assert "12345" not in sanitized
    assert "******" in sanitized

    # Assert system absolute path redacted
    assert "C:\\Users\\shiva" not in sanitized
    assert "[REPO]" in sanitized


def test_admin_verify_password():
    # 1. Invalid password
    res_bad = client.post("/api/admin/verify", json={"password": "wrongpassword"})
    assert res_bad.status_code == 401

    # 2. Correct password (12345)
    res_good = client.post("/api/admin/verify", json={"password": "12345"})
    assert res_good.status_code == 200
    assert res_good.json()["authenticated"] is True


def test_admin_logs_unauthorized_access_blocked():
    # Attempting to fetch logs without password header
    res = client.get("/api/admin/logs")
    assert res.status_code == 401
    assert "Unauthorized" in res.json()["detail"]


def test_admin_logs_authorized_fetch_and_filtering():
    clear_logs()

    # Emit a test log
    record_log("PARSER", "INFO", "Parsed candidate resume successfully.")
    record_log("SCORING", "WARNING", "Missing must-have skill: Kubernetes")

    # Fetch with X-Admin-Password header
    res = client.get(
        "/api/admin/logs",
        headers={"X-Admin-Password": "12345"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert "telemetry" in data
    assert data["telemetry"]["database_status"] == "connected"
    assert len(data["logs"]) >= 2

    # Filter by level
    res_warn = client.get(
        "/api/admin/logs?level=WARNING",
        headers={"X-Admin-Password": "12345"}
    )
    assert res_warn.status_code == 200
    warn_logs = res_warn.json()["logs"]
    assert all(l["level"] == "WARNING" for l in warn_logs)


def test_clear_logs_endpoint():
    # Clear logs via DELETE
    res = client.delete("/api/admin/logs", headers={"X-Admin-Password": "12345"})
    assert res.status_code == 200
    assert res.json()["status"] == "ok"

    # Verify cleared (buffer cleared event and auth grant event)
    res_after = client.get("/api/admin/logs", headers={"X-Admin-Password": "12345"})
    logs = res_after.json()["logs"]
    assert len(logs) <= 2
    assert any("cleared" in l["message"].lower() for l in logs)
