import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


DEFAULT_DB = Path(__file__).resolve().parents[1] / "data.sqlite3"


def connect() -> sqlite3.Connection:
    path = Path(os.getenv("DATABASE_PATH", str(DEFAULT_DB)))
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(path))
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def initialize_database() -> None:
    with connect() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS tickets (
                id TEXT PRIMARY KEY,
                source_key TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'demo',
                summary TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                comments TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'Open',
                priority TEXT NOT NULL DEFAULT '',
                assignee TEXT NOT NULL DEFAULT '',
                component TEXT NOT NULL DEFAULT '',
                created TEXT NOT NULL,
                updated TEXT NOT NULL,
                source_url TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS analyses (
                ticket_id TEXT PRIMARY KEY REFERENCES tickets(id) ON DELETE CASCADE,
                result_json TEXT NOT NULL,
                analyzed_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id TEXT NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
                rating TEXT NOT NULL,
                note TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS audit_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action TEXT NOT NULL,
                ticket_id TEXT NOT NULL DEFAULT '',
                detail TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sync_state (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                updated_cursor TEXT NOT NULL DEFAULT '',
                last_success_at TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS sync_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT NOT NULL,
                finished_at TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL,
                synced_count INTEGER NOT NULL DEFAULT 0,
                updated_cursor TEXT NOT NULL DEFAULT '',
                error TEXT NOT NULL DEFAULT ''
            );
            """
        )
        connection.execute("INSERT OR IGNORE INTO sync_state (id) VALUES (1)")
        if connection.execute("SELECT COUNT(*) FROM tickets").fetchone()[0] == 0:
            seed_demo_tickets(connection)


def seed_demo_tickets(connection: sqlite3.Connection) -> None:
    now = utc_now()
    samples = [
        (
            "DEMO-1042", "DEMO-1042", "demo", "iLO login fails after firmware update",
            "Production login to the server's iLO interface returns AUTH-401 after a recent firmware update. Two administrators are affected.",
            "Tried a different browser; the same error appears.", "In Progress", "High", "Platform Operations", "",
            now, now, "",
        ),
        (
            "DEMO-1038", "DEMO-1038", "demo", "OneView inventory sync times out",
            "HPE OneView inventory synchronization times out for one enclosure. The issue began this morning; no OneView version or task log is attached.",
            "Checked network connectivity to the management appliance.", "Open", "Medium", "Infrastructure", "",
            now, now, "",
        ),
        (
            "DEMO-1029", "DEMO-1029", "demo", "ProLiant host reports storage warning 0xA17",
            "A ProLiant host reports storage warning 0xA17. The alert is present in the management console, but the affected drive bay and firmware version are not known.",
            "", "Open", "High", "Compute Support", "",
            now, now, "",
        ),
        (
            "DEMO-1016", "DEMO-1016", "demo", "Request access to switch configuration",
            "Please provide read access to the network switch configuration for the change review. The requester did not specify the device name or review date.",
            "", "Waiting for customer", "Low", "Network Operations", "",
            now, now, "",
        ),
        (
            "DEMO-1004", "DEMO-1004", "demo", "Dashboard report is missing recent records",
            "The weekly dashboard does not show records added yesterday. Other reports appear current. Please confirm the dashboard name and the expected reporting window.",
            "Compared the dashboard with the export; the export contains the records.", "Resolved", "Medium", "Business Systems", "",
            now, now, "",
        ),
    ]
    connection.executemany(
        """INSERT INTO tickets (
            id, source_key, source, summary, description, comments, status, priority,
            assignee, component, created, updated, source_url
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        samples,
    )


def ticket_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    return dict(row)


def list_tickets(query: str = "", status: str = "", priority: str = "") -> List[Dict[str, Any]]:
    clauses = []
    values: List[str] = []
    if query:
        clauses.append("(id LIKE ? OR summary LIKE ? OR description LIKE ? OR comments LIKE ?)")
        wildcard = "%" + query + "%"
        values.extend([wildcard] * 4)
    if status:
        clauses.append("status = ?")
        values.append(status)
    if priority:
        clauses.append("priority = ?")
        values.append(priority)
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    with connect() as connection:
        rows = connection.execute(
            "SELECT tickets.*, EXISTS(SELECT 1 FROM analyses WHERE analyses.ticket_id = tickets.id) AS analyzed "
            "FROM tickets" + where + " ORDER BY updated DESC, id DESC",
            values,
        ).fetchall()
    return [ticket_to_dict(row) for row in rows]


def get_ticket(ticket_id: str) -> Optional[Dict[str, Any]]:
    with connect() as connection:
        row = connection.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
    return ticket_to_dict(row) if row else None


def save_analysis(ticket_id: str, result: Dict[str, Any]) -> str:
    analyzed_at = utc_now()
    with connect() as connection:
        connection.execute(
            "INSERT OR REPLACE INTO analyses (ticket_id, result_json, analyzed_at) VALUES (?, ?, ?)",
            (ticket_id, json.dumps(result), analyzed_at),
        )
        connection.execute(
            "INSERT INTO audit_events (action, ticket_id, detail, created_at) VALUES (?, ?, ?, ?)",
            ("analyze", ticket_id, "Rule-based analysis generated", analyzed_at),
        )
    return analyzed_at


def get_analysis(ticket_id: str) -> Optional[Dict[str, Any]]:
    with connect() as connection:
        row = connection.execute(
            "SELECT result_json, analyzed_at FROM analyses WHERE ticket_id = ?", (ticket_id,)
        ).fetchone()
    if not row:
        return None
    return {"result": json.loads(row["result_json"]), "analyzed_at": row["analyzed_at"]}


def record_feedback(ticket_id: str, rating: str, note: str) -> None:
    with connect() as connection:
        connection.execute(
            "INSERT INTO feedback (ticket_id, rating, note, created_at) VALUES (?, ?, ?, ?)",
            (ticket_id, rating, note, utc_now()),
        )
        connection.execute(
            "INSERT INTO audit_events (action, ticket_id, detail, created_at) VALUES (?, ?, ?, ?)",
            ("feedback", ticket_id, rating, utc_now()),
        )


def record_event(action: str, detail: str = "", ticket_id: str = "") -> None:
    with connect() as connection:
        connection.execute(
            "INSERT INTO audit_events (action, ticket_id, detail, created_at) VALUES (?, ?, ?, ?)",
            (action, ticket_id, detail[:500], utc_now()),
        )


def list_audit_events(limit: int = 100) -> List[Dict[str, Any]]:
    with connect() as connection:
        rows = connection.execute(
            "SELECT * FROM audit_events ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(row) for row in rows]


def get_sync_state() -> Dict[str, str]:
    with connect() as connection:
        row = connection.execute(
            "SELECT updated_cursor, last_success_at FROM sync_state WHERE id = 1"
        ).fetchone()
    return dict(row) if row else {"updated_cursor": "", "last_success_at": ""}


def start_sync_run() -> int:
    started_at = utc_now()
    with connect() as connection:
        cursor = connection.execute(
            "INSERT INTO sync_runs (started_at, status) VALUES (?, ?)",
            (started_at, "running"),
        )
        connection.execute(
            "INSERT INTO audit_events (action, detail, created_at) VALUES (?, ?, ?)",
            ("sync_started", "Jira read-only sync started", started_at),
        )
        return int(cursor.lastrowid)


def finish_sync_run(
    run_id: int,
    status: str,
    synced_count: int = 0,
    updated_cursor: str = "",
    error: str = "",
) -> None:
    finished_at = utc_now()
    with connect() as connection:
        connection.execute(
            """UPDATE sync_runs SET finished_at = ?, status = ?, synced_count = ?,
                updated_cursor = ?, error = ? WHERE id = ?""",
            (finished_at, status, synced_count, updated_cursor, error[:500], run_id),
        )
        if status == "succeeded":
            connection.execute(
                "UPDATE sync_state SET updated_cursor = ?, last_success_at = ? WHERE id = 1",
                (updated_cursor, finished_at),
            )
        connection.execute(
            "INSERT INTO audit_events (action, detail, created_at) VALUES (?, ?, ?)",
            ("sync_" + status, error[:500] or str(synced_count) + " Jira requests synchronized", finished_at),
        )


def list_sync_runs(limit: int = 20) -> List[Dict[str, Any]]:
    with connect() as connection:
        rows = connection.execute(
            "SELECT * FROM sync_runs ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(row) for row in rows]


def upsert_ticket(ticket: Dict[str, Any]) -> None:
    fields = (
        "id", "source_key", "source", "summary", "description", "comments", "status",
        "priority", "assignee", "component", "created", "updated", "source_url",
    )
    with connect() as connection:
        existing = connection.execute(
            "SELECT * FROM tickets WHERE id = ?", (ticket.get("id", ""),)
        ).fetchone()
        incoming = tuple(ticket.get(field, "") for field in fields)
        if existing and any(existing[field] != ticket.get(field, "") for field in fields):
            connection.execute("DELETE FROM analyses WHERE ticket_id = ?", (ticket["id"],))
        connection.execute(
            """INSERT INTO tickets (
                id, source_key, source, summary, description, comments, status, priority,
                assignee, component, created, updated, source_url
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                source_key=excluded.source_key, source=excluded.source,
                summary=excluded.summary, description=excluded.description,
                comments=excluded.comments, status=excluded.status, priority=excluded.priority,
                assignee=excluded.assignee, component=excluded.component,
                created=excluded.created, updated=excluded.updated, source_url=excluded.source_url""",
            incoming,
        )