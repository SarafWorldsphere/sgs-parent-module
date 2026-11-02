from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from saraswati_tenant import SchoolMiddleware
from routers import auth, dashboard, translation, communication, debug, assessments, timetable
from startup_check import run_startup_checks
import logging

logging.basicConfig(level=logging.INFO)

run_startup_checks(raise_on_error=True)

app = FastAPI(title="Parent Dashboard API")

app.add_middleware(SchoolMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(dashboard.router, tags=["Dashboard"])
app.include_router(translation.router, tags=["Translation"])
app.include_router(communication.router)
app.include_router(debug.router)
app.include_router(assessments.router, tags=["Assessments"])
app.include_router(timetable.router)


@app.get("/")
def read_root():
    return {"message": "Parent Dashboard API is running"}
