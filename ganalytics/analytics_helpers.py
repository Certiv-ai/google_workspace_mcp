"""
Google Analytics 4 Helper Functions

Shared utilities for the GA4 Admin and Data API tools: resource-name normalization,
report request/response shaping, and GA-aware error handling that surfaces the two
common GA4 blockers (missing OAuth scopes and a missing property/account role grant).
"""

import functools
import logging
from typing import Any, Dict, List, Optional

from googleapiclient.errors import HttpError  # type: ignore

from core.api_enablement import get_api_enablement_message
from core.utils import UserInputError

logger = logging.getLogger(__name__)


def normalize_property_id(property_id: str) -> str:
    """
    Normalize a GA4 property id into its ``properties/<id>`` resource name.

    Accepts a bare numeric id ("123456789") or an already-qualified resource name
    ("properties/123456789") and always returns the qualified form.
    """
    value = str(property_id or "").strip()
    if not value:
        raise UserInputError("property_id is required")
    if value.startswith("properties/"):
        return value
    return f"properties/{value}"


def normalize_account_id(account_id: str) -> str:
    """Normalize a GA4 account id into its ``accounts/<id>`` resource name."""
    value = str(account_id or "").strip()
    if not value:
        raise UserInputError("account_id is required")
    if value.startswith("accounts/"):
        return value
    return f"accounts/{value}"


def normalize_data_stream_name(property_id: str, data_stream_id: str) -> str:
    """
    Build a fully-qualified data stream resource name.

    Accepts either a bare stream id or a full ``properties/x/dataStreams/y`` name for
    ``data_stream_id``; ``property_id`` is used only when the id is not already qualified.
    """
    value = str(data_stream_id or "").strip()
    if not value:
        raise UserInputError("data_stream_id is required")
    if value.startswith("properties/"):
        return value
    return f"{normalize_property_id(property_id)}/dataStreams/{value}"


def build_date_ranges(
    date_ranges: Optional[List[Dict[str, str]]],
) -> List[Dict[str, str]]:
    """
    Validate and normalize Data API date ranges.

    Each entry must carry ``startDate`` and ``endDate`` (GA4 accepts ISO dates like
    "2024-01-01" or relative values like "7daysAgo"/"today"/"yesterday"). An optional
    ``name`` is preserved. Defaults to the last 28 days when none are supplied.
    """
    if not date_ranges:
        return [{"startDate": "28daysAgo", "endDate": "today"}]

    normalized: List[Dict[str, str]] = []
    for index, entry in enumerate(date_ranges):
        if not isinstance(entry, dict):
            raise UserInputError(
                f"date_ranges[{index}] must be an object with startDate and endDate"
            )
        start = entry.get("startDate") or entry.get("start_date")
        end = entry.get("endDate") or entry.get("end_date")
        if not start or not end:
            raise UserInputError(
                f"date_ranges[{index}] requires both startDate and endDate"
            )
        item = {"startDate": start, "endDate": end}
        if entry.get("name"):
            item["name"] = entry["name"]
        normalized.append(item)
    return normalized


def build_named_objects(names: Optional[List[str]], label: str) -> List[Dict[str, str]]:
    """
    Turn a list of dimension or metric names into the Data API ``[{"name": ...}]`` shape.

    ``label`` is only used for error messages (e.g. "dimensions", "metrics").
    """
    if not names:
        return []
    objects: List[Dict[str, str]] = []
    for index, name in enumerate(names):
        if not isinstance(name, str) or not name.strip():
            raise UserInputError(f"{label}[{index}] must be a non-empty string")
        objects.append({"name": name.strip()})
    return objects


def format_report_response(response: Dict[str, Any]) -> Dict[str, Any]:
    """
    Flatten a Data API runReport/runRealtimeReport response into row dicts.

    Produces ``{"dimensionHeaders", "metricHeaders", "rowCount", "rows": [...]}`` where
    each row maps every dimension and metric header name to its value, so a caller can
    read results without walking the parallel header/value arrays.
    """
    dimension_headers = [h.get("name") for h in response.get("dimensionHeaders", [])]
    metric_headers = [h.get("name") for h in response.get("metricHeaders", [])]

    rows: List[Dict[str, Any]] = []
    for row in response.get("rows", []):
        flat: Dict[str, Any] = {}
        for header, cell in zip(dimension_headers, row.get("dimensionValues", [])):
            flat[header] = cell.get("value")
        for header, cell in zip(metric_headers, row.get("metricValues", [])):
            flat[header] = cell.get("value")
        rows.append(flat)

    result: Dict[str, Any] = {
        "dimensionHeaders": dimension_headers,
        "metricHeaders": metric_headers,
        "rowCount": response.get("rowCount", len(rows)),
        "rows": rows,
    }
    if "totals" in response:
        result["totals"] = response["totals"]
    if "metadata" in response:
        result["metadata"] = response["metadata"]
    return result


_GA_GRANT_HINT = (
    "This is expected until paul@certiv.ai is granted a role on the target GA4 "
    "property or account in GA Admin (Viewer for read tools, Editor/Analyst for write "
    "tools), AND the GA scopes have been added to the token by re-running "
    "bootstrap_auth.py. A GA 403 usually means the account has no role on the "
    "property, not that the request was malformed."
)


def summarize_ga_error(error: HttpError, tool_name: str, service_type: str) -> str:
    """
    Build a readable, GA-aware message for a Google API HttpError.

    Surfaces (does not swallow) 403 permission errors with the property-grant hint, since
    every GA call 403s until paul@certiv.ai has both the GA scopes and a property role.
    """
    error_details = str(error)
    status = getattr(getattr(error, "resp", None), "status", None)

    if status == 403 and "accessNotConfigured" in error_details:
        enablement = get_api_enablement_message(error_details, service_type)
        if enablement:
            return f"API error in {tool_name}: {enablement}"
        return (
            f"API error in {tool_name}: {error}. The required Google Analytics API "
            f"is not enabled for this project. Enable analyticsadmin.googleapis.com "
            f"and analyticsdata.googleapis.com in the Google Cloud Console."
        )

    if status == 403:
        return f"Permission denied (403) in {tool_name}: {error}. {_GA_GRANT_HINT}"

    if status == 401:
        return (
            f"Authentication error (401) in {tool_name}: {error}. The token is missing "
            f"or invalid; re-run bootstrap_auth.py to (re-)consent the GA scopes."
        )

    if status == 404:
        return (
            f"Not found (404) in {tool_name}: {error}. Check the property/account/stream "
            f"id and that paul@certiv.ai can see that resource."
        )

    return f"API error in {tool_name}: {error}"


def handle_ga_errors(tool_name: str, service_type: str):
    """
    Decorator that converts Google API HttpErrors from GA tools into readable messages.

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
                message = summarize_ga_error(error, tool_name, service_type)
                logger.error(message, exc_info=True)
                raise Exception(message) from error

        return wrapper

    return decorator


def require_fields(payload: Dict[str, Any], fields: List[str], label: str) -> None:
    """Raise UserInputError if any of ``fields`` is missing/empty in ``payload``."""
    missing = [f for f in fields if not payload.get(f)]
    if missing:
        raise UserInputError(f"{label} requires: {', '.join(missing)}")
