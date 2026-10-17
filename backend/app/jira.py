import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List
from urllib.parse import quote, urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class JiraConfigurationError(ValueError):
    pass


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        if isinstance(value.get("text"), str):
            return _text(value["text"])
        if "content" in value:
            return _text(value["content"])
        metadata = {"type", "version", "marks", "attrs", "localId", "id"}
        return " ".join(_text(part) for key, part in value.items() if key not in metadata)
    if isinstance(value, list):
        return " ".join(_text(part) for part in value)
    text = " ".join(str(value).split())
    text = re.sub(
        r'''(?i)\b(password|passwd|token|api[-_ ]?key|secret|authorization)\b(\s*[:=]\s*)(?:"[^"]*"|'[^']*'|[^\s,;]+)''',
        r"\1\2[REDACTED]",
        text,
    )
    return re.sub(r"(?i)\bBearer\s+[^\s,;]+", "Bearer [REDACTED]", text)


def _session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=0.4,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(["GET"]),
        respect_retry_after_header=True,
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session


def fetch_jira_tickets(updated_after: str = "") -> List[Dict[str, Any]]:
    base_url = os.getenv("JIRA_BASE_URL", "").rstrip("/")
    email = os.getenv("JIRA_EMAIL", "")
    token = os.getenv("JIRA_API_TOKEN", "")
    project = os.getenv("JIRA_PROJECT_KEY", "")
    if not all((base_url, email, token)):
        raise JiraConfigurationError("Set JIRA_BASE_URL, JIRA_EMAIL, and JIRA_API_TOKEN to sync Jira.")
    parsed_url = urlparse(base_url)
    if parsed_url.scheme != "https" or not parsed_url.hostname or parsed_url.username or parsed_url.password:
        raise JiraConfigurationError("JIRA_BASE_URL must be an HTTPS URL without embedded credentials.")
    clauses = []
    if project:
        clauses.append("project = \"" + project.replace('"', "") + "\"")
    if updated_after:
        try:
            cursor = datetime.fromisoformat(updated_after.replace("Z", "+00:00"))
        except ValueError as error:
            raise JiraConfigurationError("The saved Jira synchronization cursor is invalid.") from error
        if cursor.tzinfo is None:
            cursor = cursor.replace(tzinfo=timezone.utc)
        clauses.append('updated >= "' + cursor.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M") + '"')
    order = "ASC" if updated_after else "DESC"
    jql = (" AND ".join(clauses) + " " if clauses else "") + "ORDER BY updated " + order
    fields = "summary,description,status,priority,assignee,created,updated,comment,components"
    session = _session()
    tickets = []
    start_at = 0
    max_results = 100
    while start_at < 500:
        response = session.get(
            base_url + "/rest/api/3/search",
            params={"jql": jql, "startAt": start_at, "maxResults": max_results, "fields": fields},
            auth=(email, token),
            timeout=(5, 20),
        )
        response.raise_for_status()
        payload = response.json()
        issues = payload.get("issues", [])
        for issue in issues:
            values = issue.get("fields", {})
            comments = values.get("comment", {}).get("comments", [])
            tickets.append({
                "id": "JIRA-" + issue.get("key", ""),
                "source_key": issue.get("key", ""),
                "source": "jira",
                "summary": _text(values.get("summary")),
                "description": _text(values.get("description")),
                "comments": " ".join(_text(item.get("body")) for item in comments),
                "status": _text((values.get("status") or {}).get("name")) or "Unknown",
                "priority": _text((values.get("priority") or {}).get("name")),
                "assignee": _text((values.get("assignee") or {}).get("displayName")),
                "component": ", ".join(_text(item.get("name")) for item in values.get("components", [])),
                "created": values.get("created", ""),
                "updated": values.get("updated", ""),
                "source_url": base_url + "/browse/" + quote(issue.get("key", "")),
            })
        start_at += len(issues)
        if not issues or start_at >= int(payload.get("total", 0)):
            break
    return tickets