from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import engine, Base, DB_PREFIX
import models
from routers import auth, dashboard, translation, communication, debug, assessments, timetable
from startup_check import run_startup_checks
import logging

logging.basicConfig(level=logging.INFO)

# ── Startup table validation ──────────────────────────────────────────────────
# Checks that every table the app actively queries exists in the connected DB.
# On SGS RDS (DB_TABLE_PREFIX="sgs_") this will warn about absent legacy tables
# (e.g. sgs_teacher_parent_interaction) without blocking startup, and will raise
# immediately if a *required* table is missing instead of crashing mid-request.
run_startup_checks(raise_on_error=True)

# ── Local development only: auto-create missing tables ───────────────────────
# Runs only when DB_TABLE_PREFIX is empty (local dev, no prefix).
# Production uses DB_TABLE_PREFIX="sgs_" and manages schema via migration
# scripts (see migrate_add_recipient_name.py) — create_all() is skipped there
# to avoid requiring DDL privileges on the shared RDS instance.
if not DB_PREFIX:
    Base.metadata.create_all(bind=engine)

app = FastAPI(title="Parent Dashboard API")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # For dev purposes, restrict in prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router)          # /auth/sso-token, /auth/me — parent identity
app.include_router(dashboard.router, tags=["Dashboard"])
app.include_router(translation.router, tags=["Translation"])
app.include_router(communication.router)
app.include_router(debug.router)   # dev-only: GET /debug/seeded-students, /debug/seeded-parents
app.include_router(assessments.router, tags=["Assessments"])
app.include_router(timetable.router)

@app.get("/")
def read_root():
    return {"message": "Parent Dashboard API is running"}

