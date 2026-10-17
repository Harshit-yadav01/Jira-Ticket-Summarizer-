import os
from typing import Any, Dict, List
from urllib.parse import quote_plus, urlparse

import requests


def _search_terms(ticket: Dict[str, Any]) -> str:
    parts = [ticket.get("summary", ""), ticket.get("component", "")]
    description = ticket.get("description", "")
    parts.append(" ".join(str(description).split()[:24]))
    text = " ".join(str(part) for part in parts if part)
    return " ".join(text.split())[:240]


def _portal_url(query: str) -> str:
    return "https://support.hpe.com/connect/s/search?language=en_US&query=" + quote_plus(query)


def _validated_results(payload: Any) -> List[Dict[str, str]]:
    raw_results = payload.get("results", []) if isinstance(payload, dict) else payload
    if not isinstance(raw_results, list):
        return []
    results = []
    for item in raw_results[:10]:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title", "")).strip()
        url = str(item.get("url", "")).strip()
        parsed = urlparse(url)
        if not title or parsed.scheme != "https" or parsed.username or parsed.password or not (
            parsed.hostname == "support.hpe.com" or
            (parsed.hostname or "").endswith(".support.hpe.com")
        ):
            continue
        results.append({
            "title": title[:240],
            "url": url,
            "snippet": str(item.get("snippet", ""))[:500],
            "source": "HPE Support",
        })
    return results


def find_related_documents(ticket: Dict[str, Any]) -> List[Dict[str, str]]:
    query = _search_terms(ticket)
    endpoint = os.getenv("HPE_SEARCH_API_URL", "").strip()
    if endpoint:
        parsed = urlparse(endpoint)
        host = parsed.hostname or ""
        if parsed.scheme != "https" or not (host == "support.hpe.com" or host.endswith(".support.hpe.com")):
            raise ValueError("HPE_SEARCH_API_URL must use HTTPS on an HPE Support domain.")
        headers = {}
        api_key = os.getenv("HPE_SEARCH_API_KEY", "")
        if api_key:
            headers["Authorization"] = "Bearer " + api_key
        response = requests.get(endpoint, params={"query": query}, headers=headers, timeout=8)
        response.raise_for_status()
        return _validated_results(response.json())

    # The public portal remains the source of truth when no supported search API is configured.
    return [{
        "title": "Search HPE Support for: " + query[:100],
        "url": _portal_url(query),
        "snippet": "Opens HPE Support Center search. Configure an approved HPE search API to retrieve results in the app.",
        "source": "HPE Support Center",
    }]