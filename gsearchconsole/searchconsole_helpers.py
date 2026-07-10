"""
Google Search Console Helper Functions

Shared utilities for the Search Console tools: site-url validation, Search Analytics
request shaping, response flattening, and GSC-aware error handling that surfaces the
common blocker (the authenticated user is not a verified owner/user of the property).
"""

import functools
import logging
from typing import Any, Dict, List, Optional

from googleapiclient.errors import HttpError  # type: ignore

from core.api_enablement import get_api_enablement_message
from core.utils import UserInputError

logger = logging.getLogger(__name__)

# Search Analytics dimensions accepted by searchAnalytics.query.
VALID_DIMENSIONS = {"query", "page", "country", "device", "searchAppearance", "date"}

# Aggregation types accepted by searchAnalytics.query.
VALID_AGGREGATION_TYPES = {"auto", "byProperty", "byPage"}


def require_site_url(site_url: str) -> str:
    """
    Validate and return a Search Console property URL.

    Accepts a URL-prefix property ("https://www.example.com/") or a Domain property
    ("sc-domain:example.com"). The value is passed through unchanged; GSC matches it
    exactly against the properties the authenticated user can access.
    """
    value = str(site_url or "").strip()
    if not value:
        raise UserInputError("site_url is required")
    return value


def require_feedpath(feedpath: str) -> str:
    """Validate and return a sitemap URL (the ``feedpath`` GSC parameter)."""
    value = str(feedpath or "").strip()
    if not value:
        raise UserInputError("feedpath (sitemap URL) is required")
    return value


def normalize_dimensions(dimensions: Optional[List[str]]) -> List[str]:
    """
    Validate Search Analytics dimensions against the set GSC accepts.

    Returns the cleaned list unchanged, or an empty list when none are supplied (a
    query with no dimensions returns a single totals row).
    """
    if not dimensions:
        return []
    cleaned: List[str] = []
    for index, name in enumerate(dimensions):
        if not isinstance(name, str) or not name.strip():
            raise UserInputError(f"dimensions[{index}] must be a non-empty string")
        value = name.strip()
        if value not in VALID_DIMENSIONS:
            raise UserInputError(
                f"dimensions[{index}] '{value}' is not a valid Search Console "
                f"dimension. Valid values: {', '.join(sorted(VALID_DIMENSIONS))}."
            )
        cleaned.append(value)
    return cleaned


def build_search_analytics_body(
    start_date: str,
    end_date: str,
    dimensions: Optional[List[str]] = None,
    row_limit: Optional[int] = None,
    start_row: Optional[int] = None,
    dimension_filter_groups: Optional[List[Dict[str, Any]]] = None,
    search_type: Optional[str] = None,
    data_state: Optional[str] = None,
    aggregation_type: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Build and validate a searchAnalytics.query request body.

    ``start_date`` and ``end_date`` are required ISO dates ("YYYY-MM-DD"). Optional
    ``search_type`` (a.k.a. ``type``: web/image/video/news/discover/googleNews) and
    ``aggregation_type`` are validated where GSC constrains them.
    """
    start = str(start_date or "").strip()
    end = str(end_date or "").strip()
    if not start or not end:
        raise UserInputError("start_date and end_date are required (YYYY-MM-DD)")

    body: Dict[str, Any] = {"startDate": start, "endDate": end}

    cleaned_dimensions = normalize_dimensions(dimensions)
    if cleaned_dimensions:
        body["dimensions"] = cleaned_dimensions

    if row_limit is not None:
        if not isinstance(row_limit, int) or row_limit <= 0:
            raise UserInputError("row_limit must be a positive integer")
        # GSC caps rowLimit at 25000 per request.
        body["rowLimit"] = min(row_limit, 25000)

    if start_row is not None:
        if not isinstance(start_row, int) or start_row < 0:
            raise UserInputError("start_row must be a non-negative integer")
        body["startRow"] = start_row

    if dimension_filter_groups:
        body["dimensionFilterGroups"] = dimension_filter_groups

    if search_type:
        # GSC exposes this as "type" on the request body.
        body["type"] = search_type

    if data_state:
        body["dataState"] = data_state

    if aggregation_type:
        if aggregation_type not in VALID_AGGREGATION_TYPES:
            raise UserInputError(
                f"aggregation_type '{aggregation_type}' is invalid. Valid values: "
                f"{', '.join(sorted(VALID_AGGREGATION_TYPES))}."
            )
        body["aggregationType"] = aggregation_type

    return body


def format_search_analytics_response(response: Dict[str, Any]) -> Dict[str, Any]:
    """
    Flatten a searchAnalytics.query response into readable row dicts.

    Each returned row carries ``keys`` (the dimension values in request order) plus
    ``clicks``, ``impressions``, ``ctr``, and ``position``, so a caller can read the
    metrics without walking GSC's raw shape.
    """
    rows: List[Dict[str, Any]] = []
    for row in response.get("rows", []):
        rows.append(
            {
                "keys": row.get("keys", []),
                "clicks": row.get("clicks"),
                "impressions": row.get("impressions"),
                "ctr": row.get("ctr"),
                "position": row.get("position"),
            }
        )
    result: Dict[str, Any] = {
        "rowCount": len(rows),
        "rows": rows,
    }
    if "responseAggregationType" in response:
        result["responseAggregationType"] = response["responseAggregationType"]
    return result


_GSC_ACCESS_HINT = (
    "Search Console only returns properties the authenticated user is a verified "
    "owner or user of. A 403 usually means the property is not in this account, not "
    "that the request was malformed. Confirm the exact site_url (URL-prefix like "
    "'https://www.example.com/' or a Domain property like 'sc-domain:example.com') is "
    "listed by list_search_console_sites, and that the property is shared with the "
    "authenticated Google account in Search Console."
)


def summarize_gsc_error(error: HttpError, tool_name: str) -> str:
    """
    Build a readable, GSC-aware message for a Google API HttpError.

    Surfaces (does not swallow) 403 permission errors with the property-access hint,
    since a GSC 403 almost always means the account is not an owner/user of the
    property rather than a bad request.
    """
    error_details = str(error)
    status = getattr(getattr(error, "resp", None), "status", None)

    if status == 403 and "accessNotConfigured" in error_details:
        enablement = get_api_enablement_message(error_details, "searchconsole")
        if enablement:
            return f"API error in {tool_name}: {enablement}"
        return (
            f"API error in {tool_name}: {error}. The Search Console API is not enabled "
            f"for this project. Enable searchconsole.googleapis.com in the Google "
            f"Cloud Console."
        )

    if status == 403:
        return f"Permission denied (403) in {tool_name}: {error}. {_GSC_ACCESS_HINT}"

    if status == 401:
        return (
            f"Authentication error (401) in {tool_name}: {error}. The token is missing "
            f"or invalid; re-run the auth flow to (re-)consent the Search Console "
            f"(webmasters) scopes."
        )

    if status == 404:
        return (
            f"Not found (404) in {tool_name}: {error}. Check the site_url / sitemap "
            f"feedpath and that the authenticated account can see that resource."
        )

    return f"API error in {tool_name}: {error}"


def handle_gsc_errors(tool_name: str):
    """
    Decorator that converts Google API HttpErrors from GSC tools into readable messages.

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
                message = summarize_gsc_error(error, tool_name)
                logger.error(message, exc_info=True)
                raise Exception(message) from error

        return wrapper

    return decorator
