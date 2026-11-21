"""
Live Logging and Security Diagnostic Engine.
Provides in-memory circular log buffering, PII sanitization, brute-force protection,
and telemetry for real-time observability without data leaks.
"""

import os
import re
import time
import secrets
import threading
from collections import deque
from datetime import datetime
from typing import List, Dict, Any, Optional

# Admin Password Configuration (Default: 12345, overridable via env var)
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "12345")

# Thread-safe in-memory ring buffer (max 2,500 records)
MAX_LOG_ENTRIES = 2500
_log_buffer: deque = deque(maxlen=MAX_LOG_ENTRIES)
_log_lock = threading.Lock()
_log_counter = 0
_start_time = time.time()

# Security & brute-force rate limiting: ip -> list of failed attempt timestamps
_failed_attempts: Dict[str, List[float]] = {}
_failed_lock = threading.Lock()
LOCKOUT_WINDOW_SECONDS = 60
MAX_FAILED_ATTEMPTS = 5

# Regular expressions for PII redaction and path sanitization
RE_EMAIL = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
RE_PHONE = re.compile(r'\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b')
RE_WINDOWS_PATH = re.compile(r'[A-Za-z]:\\[^ \n\r\t:]+')
RE_UNIX_PATH = re.compile(r'/(?:home|Users|var|etc|tmp)/[^ \n\r\t:]+')


def sanitize_text(text: str) -> str:
    """
    Sanitizes log messages to prevent PII and sensitive path disclosure.
    Redacts candidate emails, phone numbers, and internal system directory paths.
    """
    if not isinstance(text, str):
        text = str(text)

    # Redact email addresses: e.g. j***@example.com
    def _mask_email(match):
        val = match.group(0)
        parts = val.split('@')
        if len(parts) == 2 and len(parts[0]) > 1:
            return f"{parts[0][0]}***@{parts[1]}"
        return "[EMAIL_REDACTED]"

    # Redact phone numbers
    text = RE_EMAIL.sub(_mask_email, text)
    text = RE_PHONE.sub("[PHONE_REDACTED]", text)

    # Sanitize internal directory paths
    text = RE_WINDOWS_PATH.sub(lambda m: "[REPO]\\" + os.path.basename(m.group(0)), text)
    text = RE_UNIX_PATH.sub(lambda m: "[REPO]/" + os.path.basename(m.group(0)), text)

    # Mask admin password occurrences if accidentally printed
    if ADMIN_PASSWORD and len(ADMIN_PASSWORD) >= 3:
        text = text.replace(ADMIN_PASSWORD, "******")

    return text


def record_log(
    subsystem: str,
    level: str,
    message: str,
    details: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Records a structured, sanitized log event into the thread-safe ring buffer.
    """
    global _log_counter
    sanitized_msg = sanitize_text(message)
    sanitized_details = None

    if details:
        sanitized_details = {}
        for k, v in details.items():
            if isinstance(v, str):
                sanitized_details[k] = sanitize_text(v)
            elif isinstance(v, (int, float, bool)):
                sanitized_details[k] = v
            else:
                sanitized_details[k] = sanitize_text(str(v))

    entry = {
        "id": 0,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
        "subsystem": subsystem.upper(),
        "level": level.upper(),
        "message": sanitized_msg,
        "details": sanitized_details or {},
    }

    with _log_lock:
        _log_counter += 1
        entry["id"] = _log_counter
        _log_buffer.append(entry)

    return entry


def get_logs(
    since_id: int = 0,
    level: Optional[str] = None,
    subsystem: Optional[str] = None,
    limit: int = 150
) -> List[Dict[str, Any]]:
    """
    Retrieves filtered logs from the circular buffer.
    """
    with _log_lock:
        records = list(_log_buffer)

    filtered = []
    level_filter = level.upper() if level and level.upper() != "ALL" else None
    subsystem_filter = subsystem.upper() if subsystem and subsystem.upper() != "ALL" else None

    for item in records:
        if item["id"] <= since_id:
            continue
        if level_filter and item["level"] != level_filter:
            continue
        if subsystem_filter and item["subsystem"] != subsystem_filter:
            continue
        filtered.append(item)

    if limit and len(filtered) > limit:
        filtered = filtered[-limit:]

    return filtered


def clear_logs() -> None:
    """Clears all buffered log records."""
    with _log_lock:
        _log_buffer.clear()
    record_log("SYSTEM", "INFO", "Log buffer cleared by admin.")


def verify_admin_password(provided_password: str, client_ip: str = "127.0.0.1") -> bool:
    """
    Verifies admin password with brute-force protection and timing-safe comparison.
    """
    now = time.time()

    with _failed_lock:
        # Purge expired attempts outside lockout window
        attempts = _failed_attempts.get(client_ip, [])
        attempts = [t for t in attempts if now - t < LOCKOUT_WINDOW_SECONDS]
        _failed_attempts[client_ip] = attempts

        if len(attempts) >= MAX_FAILED_ATTEMPTS:
            record_log(
                "SECURITY",
                "WARNING",
                f"Authentication locked out for IP: {client_ip} (Too many failed attempts)."
            )
            return False

        # Constant-time comparison to prevent side-channel timing attacks
        is_valid = secrets.compare_digest(str(provided_password), str(ADMIN_PASSWORD))

        if not is_valid:
            _failed_attempts[client_ip].append(now)
            record_log(
                "SECURITY",
                "WARNING",
                f"Failed admin authentication attempt from IP: {client_ip}."
            )
        else:
            # Clear failed attempts on successful verification
            _failed_attempts.pop(client_ip, None)
            record_log("SECURITY", "INFO", f"Admin access granted for IP: {client_ip}.")

        return is_valid


def get_telemetry_status(db_session=None) -> Dict[str, Any]:
    """
    Computes real-time telemetry metrics across all subsystems.
    """
    with _log_lock:
        records = list(_log_buffer)

    error_count = sum(1 for r in records if r["level"] in ("ERROR", "CRITICAL"))
    warn_count = sum(1 for r in records if r["level"] == "WARNING")
    uptime = round(time.time() - _start_time, 1)

    # Check model files status
    models_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "models")
    model_loaded = os.path.exists(models_dir) and len([f for f in os.walk(models_dir) if any(x.endswith(".onnx") for x in f[2])]) > 0

    # Optional DB counters
    total_jobs = 0
    total_candidates = 0
    db_status = "connected"

    if db_session:
        try:
            from app.models import Job, Candidate
            total_jobs = db_session.query(Job).count()
            total_candidates = db_session.query(Candidate).count()
        except Exception as e:
            db_status = f"error: {str(e)}"

    return {
        "status": "healthy" if error_count == 0 else "degraded" if error_count < 5 else "attention_required",
        "uptime_seconds": uptime,
        "total_logs": len(records),
        "error_count": error_count,
        "warning_count": warn_count,
        "model_loaded": model_loaded,
        "model_name": "BAAI/bge-small-en-v1.5 (ONNX Quantized, 384d)",
        "database_status": db_status,
        "total_jobs": total_jobs,
        "total_candidates": total_candidates,
    }


# Initial boot log
record_log("SYSTEM", "INFO", "Live Diagnostic Logger initialized successfully.")
