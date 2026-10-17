import hmac
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator, Optional

import requests
from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from app.analysis import summarize_ticket
from app.database import (
    get_analysis,
    get_sync_state,
    get_ticket,
    initialize_database,
    list_audit_events,
    list_sync_runs,
    list_tickets,
    finish_sync_run,
    record_event,
    record_feedback,
    save_analysis,
    start_sync_run,
    upsert_ticket,
)
from app.hpe import find_related_documents
from app.jira import JiraConfigurationError, fetch_jira_tickets


def _perform_jira_sync():
    state = get_sync_state()
    run_id = start_sync_run()
    try:
        tickets = fetch_jira_tickets(updated_after=state["updated_cursor"])
        for ticket in tickets:
            upsert_ticket(ticket)
        cursor_values = [ticket["updated"] for ticket in tickets if ticket.get("updated")]
        updated_cursor = max(cursor_values) if cursor_values else state["updated_cursor"]
        finish_sync_run(run_id, "succeeded", len(tickets), updated_cursor)
        return {"synced": len(tickets), "updated_cursor": updated_cursor}
    except Exception as error:
        finish_sync_run(run_id, "failed", error=str(error))
        raise


def _scheduled_jira_sync() -> None:
    try:
        _perform_jira_sync()
    except (JiraConfigurationError, requests.RequestException):
        pass


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    interval_minutes = int(os.getenv("JIRA_SYNC_INTERVAL_MINUTES", "0"))
    scheduler = None
    if interval_minutes > 0:
        scheduler = BackgroundScheduler(timezone="UTC")
        scheduler.add_job(
            _scheduled_jira_sync,
            "interval",
            minutes=interval_minutes,
            id="jira-sync",
            max_instances=1,
            coalesce=True,
            replace_existing=True,
        )
        scheduler.start()
    try:
        yield
    finally:
        if scheduler:
            scheduler.shutdown(wait=False)


app = FastAPI(title="Request Lens", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(","),
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-API-Key"],
)
initialize_database()


def _resolve_role(x_api_key: Optional[str]) -> str:
    viewer_key = os.getenv("APP_VIEWER_API_KEY", "")
    analyst_key = os.getenv("APP_ANALYST_API_KEY", "") or os.getenv("APP_API_KEY", "")
    if not viewer_key and not analyst_key:
        return "analyst"
    supplied = x_api_key or ""
    if analyst_key and hmac.compare_digest(supplied, analyst_key):
        return "analyst"
    if viewer_key and hmac.compare_digest(supplied, viewer_key):
        return "viewer"
    raise HTTPException(status_code=401, detail="A valid workspace API key is required.")


def require_viewer(x_api_key: Optional[str] = Header(default=None, alias="X-API-Key")) -> str:
    return _resolve_role(x_api_key)


def require_analyst(x_api_key: Optional[str] = Header(default=None, alias="X-API-Key")) -> str:
    if _resolve_role(x_api_key) != "analyst":
        raise HTTPException(status_code=403, detail="Analyst access is required for this action.")
    return "analyst"


def _api_key_configured() -> bool:
    if os.getenv("APP_VIEWER_API_KEY", "") or os.getenv("APP_ANALYST_API_KEY", "") or os.getenv("APP_API_KEY", ""):
        return True
    return False


class FeedbackInput(BaseModel):
    rating: str = Field(pattern="^(useful|not_useful)$")
    note: str = Field(default="", max_length=1000)


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/config")
def public_config():
    sync_state = get_sync_state()
    return {
        "api_key_required": _api_key_configured(),
        "role_keys_configured": bool(os.getenv("APP_VIEWER_API_KEY", "") or os.getenv("APP_ANALYST_API_KEY", "")),
        "jira_configured": all(os.getenv(name, "") for name in ("JIRA_BASE_URL", "JIRA_EMAIL", "JIRA_API_TOKEN")),
        "hpe_search_configured": bool(os.getenv("HPE_SEARCH_API_URL", "")),
        "last_sync_at": sync_state["last_success_at"],
        "sync_interval_minutes": int(os.getenv("JIRA_SYNC_INTERVAL_MINUTES", "0")),
        "mode": "jira" if all(os.getenv(name, "") for name in ("JIRA_BASE_URL", "JIRA_EMAIL", "JIRA_API_TOKEN")) else "demo",
    }


@app.get("/api/requests", dependencies=[Depends(require_viewer)])
def requests_list(
    q: str = Query(default="", max_length=200),
    status: str = Query(default="", max_length=100),
    priority: str = Query(default="", max_length=100),
):
    tickets = list_tickets(query=q.strip(), status=status.strip(), priority=priority.strip())
    for ticket in tickets:
        ticket["analyzed"] = bool(ticket["analyzed"])
    return {"items": tickets, "total": len(tickets)}


@app.get("/api/requests/{ticket_id}", dependencies=[Depends(require_viewer)])
def request_detail(ticket_id: str):
    ticket = get_ticket(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Request not found.")
    saved_analysis = get_analysis(ticket_id)
    return {
        "ticket": ticket,
        "analysis": saved_analysis["result"] if saved_analysis else None,
        "analyzed_at": saved_analysis["analyzed_at"] if saved_analysis else None,
    }


@app.post("/api/requests/{ticket_id}/analyze", dependencies=[Depends(require_analyst)])
def analyze_request(ticket_id: str):
    ticket = get_ticket(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Request not found.")
    analysis = summarize_ticket(ticket)
    try:
        documents = find_related_documents(ticket)
        documents_error = ""
    except (ValueError, requests.RequestException) as error:
        documents = []
        documents_error = str(error)[:300]
    stored_result = {"analysis": analysis, "documents": documents, "documents_error": documents_error}
    analyzed_at = save_analysis(ticket_id, stored_result)
    return {"ticket": ticket, **stored_result, "analyzed_at": analyzed_at}


@app.post("/api/requests/{ticket_id}/feedback", dependencies=[Depends(require_analyst)])
def submit_feedback(ticket_id: str, feedback: FeedbackInput):
    if not get_ticket(ticket_id):
        raise HTTPException(status_code=404, detail="Request not found.")
    record_feedback(ticket_id, feedback.rating, feedback.note)
    return {"saved": True}


@app.post("/api/sync", dependencies=[Depends(require_analyst)])
def sync_requests():
    try:
        return _perform_jira_sync()
    except JiraConfigurationError as error:
        raise HTTPException(status_code=400, detail=str(error))
    except requests.RequestException as error:
        raise HTTPException(status_code=502, detail="Jira sync failed. Check connection settings and server logs.")


@app.get("/api/sync/history", dependencies=[Depends(require_viewer)])
def sync_history():
    return {"items": list_sync_runs(20)}


@app.get("/api/audit", dependencies=[Depends(require_viewer)])
def audit_events():
    return {"items": list_audit_events(100)}


frontend_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if frontend_dist.exists():
    assets_dir = frontend_dist / "assets"
    if assets_dir.exists():
        from fastapi.staticfiles import StaticFiles

        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    @app.get("/{path:path}")
    def serve_frontend(path: str):
        candidate = (frontend_dist / path).resolve()
        if candidate.is_file() and frontend_dist.resolve() in candidate.parents:
            return FileResponse(candidate)
        index_file = frontend_dist / "index.html"
        if index_file.is_file():
            return FileResponse(index_file)
        return JSONResponse({"message": "Frontend build is missing."}, status_code=404)
else:
    @app.get("/")
    def root():
        return {"name": "Request Lens", "api": "/docs", "frontend": "Run the Vite app in frontend/."}