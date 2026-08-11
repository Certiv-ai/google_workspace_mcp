"""
Google Workspace Alert Center Helper Functions

Shared utilities for the Alert Center read and feedback tools: argument validation,
list-filter and feedback-body shaping, alert summarization, and Alert-Center-aware error
handling that surfaces the two common blockers (missing OAuth scope and the auth'd user
not being a Google Workspace admin with Alert Center access).
"""

import functools
import logging
from typing import Any

from googleapiclient.errors import HttpError  # type: ignore

from core.api_enablement import get_api_enablement_message
from core.utils import UserInputError

logger = logging.getLogger(__name__)

# Feedback types accepted by alerts.feedback.create. This is how an admin marks an alert
# useful or not useful; it is non-destructive (it never deletes or hides the alert).
VALID_FEEDBACK_TYPES = frozenset(
    {
        "ALERT_FEEDBACK_TYPE_UNSPECIFIED",
        "NOT_USEFUL",
        "SOMEWHAT_USEFUL",
        "VERY_USEFUL",
    }
)


def require_non_empty(value: str, label: str) -> str:
    """Return a stripped string, raising UserInputError when it is missing/empty."""
    text = str(value or "").strip()
    if not text:
        raise UserInputError(f"{label} is required")
    return text


def _quote(value: str) -> str:
    """Wrap a filter value in double quotes, escaping any embedded quotes/backslashes."""
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def build_alerts_filter(
    alert_type: str | None = None,
    source: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
) -> str | None:
    """
    Build an Alert Center ``alerts.list`` filter string from structured arguments.

    Uses the Alert Center filter syntax (a subset of AIP-160). ``alert_type`` maps to the
    ``type`` field and ``source`` to the ``source`` field; ``start_time``/``end_time``
    bound the alert ``createTime`` (RFC3339 timestamps, e.g. "2024-01-01T00:00:00Z").
    Clauses are combined with AND. Returns None when no arguments are supplied so the
    caller can omit the filter entirely.
    """
    clauses: list[str] = []
    if alert_type and str(alert_type).strip():
        clauses.append(f"type = {_quote(str(alert_type).strip())}")
    if source and str(source).strip():
        clauses.append(f"source = {_quote(str(source).strip())}")
    if start_time and str(start_time).strip():
        clauses.append(f"createTime >= {_quote(str(start_time).strip())}")
    if end_time and str(end_time).strip():
        clauses.append(f"createTime <= {_quote(str(end_time).strip())}")
    if not clauses:
        return None
    return " AND ".join(clauses)


def summarize_alert(alert: dict[str, Any]) -> dict[str, Any]:
    """
    Reduce a full Alert resource to the fields most useful in a list view.

    Surfaces identity/type/source/timestamps plus the severity (which lives under the
    alert ``metadata``) and a compact data summary (the payload ``@type`` and its
    top-level keys) so a caller can scan many alerts without walking each full payload.
    """
    metadata = alert.get("metadata") or {}
    data = alert.get("data") or {}
    data_summary: dict[str, Any] = {}
    if isinstance(data, dict):
        if data.get("@type"):
            data_summary["type"] = data.get("@type")
        data_summary["keys"] = sorted(k for k in data if k != "@type")
    return {
        "alertId": alert.get("alertId"),
        "customerId": alert.get("customerId"),
        "type": alert.get("type"),
        "source": alert.get("source"),
        "severity": metadata.get("severity"),
        "status": metadata.get("status"),
        "createTime": alert.get("createTime"),
        "startTime": alert.get("startTime"),
        "endTime": alert.get("endTime"),
        "deleted": alert.get("deleted", False),
        "dataSummary": data_summary,
    }


def format_alerts_list(response: dict[str, Any]) -> dict[str, Any]:
    """
    Flatten an ``alerts.list`` response into summarized rows plus the page token.

    Returns ``{"rowCount", "alerts": [summary, ...], "nextPageToken"}`` where each alert
    is reduced via :func:`summarize_alert`.
    """
    alerts = [summarize_alert(a) for a in response.get("alerts", [])]
    return {
        "rowCount": len(alerts),
        "alerts": alerts,
        "nextPageToken": response.get("nextPageToken"),
    }


def build_feedback_body(feedback_type: str) -> dict[str, Any]:
    """
    Validate a feedback type and shape it into an ``alerts.feedback.create`` request body.

    Raises UserInputError naming the unsupported value (with the valid set) so the caller
    gets a clear message instead of an opaque 400 from the API.
    """
    value = require_non_empty(feedback_type, "feedback_type")
    if value not in VALID_FEEDBACK_TYPES:
        raise UserInputError(
            f"feedback_type '{value}' is not supported; valid types are: "
            f"{', '.join(sorted(VALID_FEEDBACK_TYPES))}"
        )
    return {"type": value}


_ALERT_CENTER_GRANT_HINT = (
    "This is expected until paul@certiv.ai is a Google Workspace admin with Alert Center "
    "privileges, AND the apps.alerts scope has been consented on the token. An Alert "
    "Center 403/permission error almost always means the account lacks the admin role or "
    "the scope, not that the request was malformed."
)


def summarize_alert_center_error(error: HttpError, tool_name: str) -> str:
    """
    Build a readable, Alert-Center-aware message for a Google API HttpError.

    Surfaces (does not swallow) 403 permission errors with the admin-grant hint, since
    every Alert Center call 403s until paul@certiv.ai is an admin with the apps.alerts
    scope consented.
    """
    error_details = str(error)
    status = getattr(getattr(error, "resp", None), "status", None)

    if status == 403 and "accessNotConfigured" in error_details:
        enablement = get_api_enablement_message(error_details, "alertcenter")
        if enablement:
            return f"API error in {tool_name}: {enablement}"
        return (
            f"API error in {tool_name}: {error}. The Google Workspace Alert Center API "
            f"is not enabled for this project. Enable alertcenter.googleapis.com in the "
            f"Google Cloud Console."
        )

    if status == 403:
        return f"Permission denied (403) in {tool_name}: {error}. {_ALERT_CENTER_GRANT_HINT}"

    if status == 401:
        return (
            f"Authentication error (401) in {tool_name}: {error}. The token is missing "
            f"or invalid; re-consent the apps.alerts scope."
        )

    if status == 404:
        return (
            f"Not found (404) in {tool_name}: {error}. Check the alertId and that "
            f"paul@certiv.ai can see that alert."
        )

    return f"API error in {tool_name}: {error}"


def handle_alert_center_errors(tool_name: str):
    """
    Decorator that converts Google API HttpErrors from Alert Center tools into readable
    messages.

    Applied inside each tool wrapper (below @require_google_service) so the injected
    ``service`` call is covered. UserInputError is re-raised unchanged so bad arguments
    stay distinct from API/permission failures.
    """

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except UserInputError:
                raise
            except HttpError as error:
                message = summarize_alert_center_error(error, tool_name)
                logger.exception(message)
                raise RuntimeError(message) from error

        return wrapper

    return decorator
