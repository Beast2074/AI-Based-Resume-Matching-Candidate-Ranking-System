"""
AI-Based Resume Matching & Candidate Ranking System FastAPI Entrypoint.
"""

import os
import time
import traceback
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.db import init_db
from app.routers import jobs, candidates, admin
from app.services.scoring import load_scoring_config
from app.services.logger import record_log

# Ensure database tables exist immediately upon startup/import safely
try:
    init_db()
except Exception as e:
    record_log("SYSTEM", "WARNING", f"Initial DB init: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database tables on startup if missing
    record_log("SYSTEM", "INFO", "Initializing database schemas...")
    init_db()
    record_log("SYSTEM", "INFO", "AI-Based Resume Matching & Candidate Ranking System ready.")
    yield
    record_log("SYSTEM", "INFO", "System shutting down cleanly.")


app = FastAPI(
    title="AI-Based Resume Matching & Candidate Ranking System API",
    description="Explainable AI Resume Matching & Deterministic Ranking System",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS: allow localhost, environment origins, and all Vercel domains dynamically
raw_cors = os.getenv("CORS_ORIGINS", "")
origins_list = [o.strip() for o in raw_cors.split(",") if o.strip()]
default_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
for d in default_origins:
    if d not in origins_list:
        origins_list.append(d)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins_list,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def live_diagnostic_logging_middleware(request: Request, call_next):
    """
    Middleware that records API request latency and status to the diagnostic buffer.
    Catches unhandled server exceptions safely to prevent sensitive data/stack leaks.
    """
    start_time = time.time()
    path = request.url.path
    method = request.method

    # Skip high-frequency admin log polling from cluttering the logs buffer
    is_log_poll = "/api/admin/logs" in path

    try:
        response = await call_next(request)
        elapsed_ms = round((time.time() - start_time) * 1000.0, 1)

        if not is_log_poll:
            level = "INFO" if response.status_code < 400 else "WARNING" if response.status_code < 500 else "ERROR"
            record_log(
                subsystem="API",
                level=level,
                message=f"{method} {path} -> {response.status_code} ({elapsed_ms} ms)",
                details={"method": method, "path": path, "status": response.status_code, "latency_ms": elapsed_ms}
            )
        return response

    except Exception as exc:
        elapsed_ms = round((time.time() - start_time) * 1000.0, 1)
        tb_str = traceback.format_exc()
        record_log(
            subsystem="API",
            level="ERROR",
            message=f"Unhandled 500 Exception on {method} {path}: {str(exc)}",
            details={"traceback": tb_str, "latency_ms": elapsed_ms}
        )
        # Prevent stack trace / internal structure leak in public response
        return JSONResponse(
            status_code=500,
            content={"detail": "An internal server error occurred. Telemetry recorded in diagnostic logs."}
        )


# Mount Routers
app.include_router(jobs.router)
app.include_router(candidates.router)
app.include_router(admin.router)


def check_model_loaded() -> bool:
    """Checks whether the local ONNX embedding model files are present."""
    models_dir = Path(__file__).resolve().parent.parent / "models"
    if not models_dir.exists():
        return False
    onnx_files = list(models_dir.rglob("*.onnx"))
    return len(onnx_files) > 0


@app.get("/api/health")
def get_health():
    return {
        "status": "ok",
        "model_loaded": check_model_loaded(),
        "version": "0.1.0",
    }


@app.get("/api/scoring-config")
def get_scoring_config():
    """Returns the live scoring weights and thresholds from scoring.json."""
    return load_scoring_config()
