import re
from typing import Any, Dict


CATEGORY_RULES = [
    ("Access or permissions", ("permission", "access denied", "unauthorized", "login", "sign in")),
    ("Performance", ("slow", "latency", "timeout", "performance")),
    ("Integration failure", ("integration", "api", "connector", "sync", "synchronization")),
    ("Hardware or product issue", ("firmware", "hardware", "ilo", "proliant", "storage", "switch")),
    ("Application defect", ("bug", "crash", "exception", "not working", "failed", "error")),
    ("Data or reporting", ("report", "data", "missing records", "incorrect value")),
    ("Service request", ("request", "please enable", "please provide", "install", "upgrade")),
]

PRODUCT_TERMS = (
    "HPE OneView", "HPE iLO", "HPE ProLiant", "HPE Alletra", "HPE MSA", "HPE Aruba",
    "OneView", "iLO", "ProLiant", "Alletra", "Aruba", "HPE",
)

ERROR_PATTERN = re.compile(
    r"\b(?:0x[0-9a-fA-F]+|[A-Z]{2,}[A-Z0-9_-]*\d[A-Z0-9_-]*|\d{3,})\b"
)
ACTION_PATTERN = re.compile(
    r"[^.!?]*(?:tried|attempted|restarted|rebooted|installed|updated|rolled back|checked)[^.!?]*[.!?]?",
    re.IGNORECASE,
)


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        return " ".join(_text(item) for item in value.values())
    if isinstance(value, list):
        return " ".join(_text(item) for item in value)
    return re.sub(r"\s+", " ", str(value)).strip()


def _priority_impact(priority: str) -> str:
    normalized = priority.lower()
    if any(term in normalized for term in ("highest", "blocker", "critical", "urgent")):
        return "The ticket is marked with the highest urgency; confirm the number of affected users and services."
    if any(term in normalized for term in ("high", "major")):
        return "The ticket is marked high priority; confirm the operational impact and scope."
    if priority:
        return "The source ticket priority is " + priority + "."
    return "Impact is not specified in the ticket."


def _category(text: str) -> str:
    lowered = text.lower()
    for category, terms in CATEGORY_RULES:
        if any(term in lowered for term in terms):
            return category
    return "Needs review"


def summarize_ticket(ticket: Dict[str, Any]) -> Dict[str, Any]:
    """Create a transparent, rule-based analysis without generating new facts."""
    title = _text(ticket.get("summary") or ticket.get("title"))
    description = _text(ticket.get("description"))
    comments = _text(ticket.get("comments"))
    source_text = " ".join(part for part in (title, description, comments) if part)
    priority = _text(ticket.get("priority"))

    short_description = description or "The ticket does not include a detailed description."
    if len(short_description) > 420:
        short_description = short_description[:417].rsplit(" ", 1)[0] + "..."

    product = next(
        (term for term in PRODUCT_TERMS if re.search(re.escape(term), source_text, re.IGNORECASE)),
        _text(ticket.get("component")) or "Not identified from the ticket",
    )
    errors = list(dict.fromkeys(ERROR_PATTERN.findall(source_text)))
    actions = [match.strip() for match in ACTION_PATTERN.findall(source_text) if match.strip()]
    missing = []
    if not re.search(r"\b(?:production|prod|staging|stage|test|development|dev)\b", source_text, re.I):
        missing.append("Affected environment")
    if not errors:
        missing.append("Exact error message or code, if one is shown")
    if not actions:
        missing.append("Troubleshooting steps already attempted")
    has_version = re.search(
        r"\b(?:version|firmware|release)\s*(?:v)?\d+(?:\.\d+){0,3}\b|\bv\d+(?:\.\d+){1,3}\b",
        source_text,
        re.I,
    )
    if not has_version:
        missing.append("Product, software, or firmware version")

    quick = short_description
    if title and description:
        quick = title.rstrip(". ") + ": " + short_description
    elif title:
        quick = title

    return {
        "quick_summary": quick,
        "problem_statement": short_description,
        "expected_outcome": "Not explicitly stated in the ticket.",
        "actual_vs_expected": "The ticket does not provide enough detail to compare expected and actual behavior.",
        "impact": _priority_impact(priority),
        "category": _category(source_text),
        "affected_product": product,
        "error_evidence": errors,
        "actions_attempted": actions,
        "missing_information": missing,
        "confirmed_facts": [value for value in (title, "Priority: " + priority if priority else "") if value],
        "inferences": [],
        "recommended_next_steps": [
            "Confirm the affected environment, product version, and scope of impact.",
            "Collect the exact error text and relevant logs before changing the system.",
            "Compare the symptoms with the linked HPE Support documentation and follow only steps that match this product and version.",
        ],
        "analysis_method": "Deterministic field extraction and keyword rules; no language model is used.",
    }