"""
Admin & System Diagnostics API Router.
Endpoints:
- POST /api/admin/verify: Authenticates admin credentials
- GET  /api/admin/logs: Retrieves sanitized system logs and telemetry (Password protected)
- DELETE /api/admin/logs: Clears in-memory log buffer (Password protected)
- POST /api/admin/test-event: Injects a test diagnostic event
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Header, Query, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.services.logger import (
    verify_admin_password,
    get_logs,
    clear_logs,
    record_log,
    get_telemetry_status,
)

router = APIRouter(prefix="/api/admin", tags=["admin"])


class AdminVerifyRequest(BaseModel):
    password: str


class AdminVerifyResponse(BaseModel):
    authenticated: bool
    message: str


class TestEventRequest(BaseModel):
    subsystem: str = "TEST"
    level: str = "INFO"
    message: str


def get_client_ip(request: Request) -> str:
    """Extract client IP address safely, respecting reverse proxies."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "127.0.0.1"


def authenticate_admin(
    request: Request,
    x_admin_password: Optional[str] = Header(None, alias="X-Admin-Password"),
    password_query: Optional[str] = Query(None, alias="password"),
) -> bool:
    """Dependency that enforces admin authentication."""
    provided = x_admin_password or password_query or ""
    client_ip = get_client_ip(request)

    if not provided or not verify_admin_password(provided, client_ip):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: Invalid or missing admin credentials.",
            headers={"WWW-Authenticate": "Admin-Password"},
        )
    return True


@router.post("/verify", response_model=AdminVerifyResponse)
def verify_admin(payload: AdminVerifyRequest, request: Request):
    """Verifies the admin password (default: 12345)."""
    client_ip = get_client_ip(request)
    if not verify_admin_password(payload.password, client_ip):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect admin password. Access denied.",
        )
    return AdminVerifyResponse(
        authenticated=True,
        message="Admin authentication successful. Diagnostic telemetry unlocked."
    )


@router.get("/logs")
def fetch_system_logs(
    request: Request,
    since_id: int = Query(0, ge=0),
    level: Optional[str] = Query(None),
    subsystem: Optional[str] = Query(None),
    limit: int = Query(150, ge=1, le=1000),
    auth: bool = Depends(authenticate_admin),
    db: Session = Depends(get_db),
):
    """
    Returns sanitized real-time system logs and engine telemetry.
    Strictly protected by admin authentication to prevent log and data leaks.
    """
    logs = get_logs(since_id=since_id, level=level, subsystem=subsystem, limit=limit)
    telemetry = get_telemetry_status(db_session=db)

    return {
        "status": "ok",
        "telemetry": telemetry,
        "count": len(logs),
        "logs": logs,
    }


@router.delete("/logs")
def clear_system_logs(
    auth: bool = Depends(authenticate_admin),
):
    """Clears buffered system diagnostic logs."""
    clear_logs()
    return {"status": "ok", "message": "Diagnostic log buffer cleared."}


@router.post("/test-event")
def emit_test_event(
    payload: TestEventRequest,
    auth: bool = Depends(authenticate_admin),
):
    """Emits a manual diagnostic test event for verification."""
    entry = record_log(
        subsystem=payload.subsystem,
        level=payload.level,
        message=payload.message,
        details={"source": "admin_ui_test"}
    )
    return {"status": "ok", "event": entry}
