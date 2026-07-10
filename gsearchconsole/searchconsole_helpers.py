"""
Google Search Console Helper Functions

Shared utilities for the Search Console read and sitemap-write tools: argument
validation, search-analytics request/response shaping, and Search-Console-aware error
handling that surfaces the two common blockers (missing OAuth scopes and the auth'd user
not being a verified owner/user of the target property).
"""

import functools
import logging
from typing import Any, Dict, List, Optional

from googleapiclient.errors import HttpError  # type: ignore

from core.api_enablement import get_api_enablement_message
from core.utils import UserInputError

logger = logging.getLogger(__name__)

# Search Analytics query dimensions accepted by the API.
VALID_DIMENSIONS = frozenset(
    {"query", "page", "country", "device", "searchAppearance", "date"}
)

# Search Analytics "type" (search type) values accepted by the API.
VALID_SEARCH_TYPES = frozenset(
    {"web", "image", "video", "news", "discover", "googleNews"}
)


def require_non_empty(value: str, label: str) -> str:
    """Return a stripped string, raising UserInputError when it is missing/empty."""
    text = str(value or "").strip()
    if not text:
        raise UserInputError(f"{label} is required")
    return text


def validate_dimensions(dimensions: Optional[List[str]]) -> List[str]:
    """
    Validate Search Analytics dimensions against the API's accepted set.

    Returns the list unchanged (or an empty list when none are supplied). Raises
    UserInputError naming any unsupported dimension so the caller gets a clear message
    instead of an opaque 400 from the API.
    """
    if not dimensions:
        return []
    cleaned: List[str] = []
    for index, dimension in enumerate(dimensions):
        name = str(dimension or "").strip()
        if not name:
            raise UserInputError(f"dimensions[{index}] must be a non-empty string")
        if name not in VALID_DIMENSIONS:
            raise UserInputError(
                f"dimensions[{index}] '{name}' is not supported; valid dimensions are: "
                f"{', '.join(sorted(VALID_DIMENSIONS))}"
            )
        cleaned.append(name)
    return cleaned


def validate_search_type(search_type: Optional[str]) -> Optional[str]:
    """
    Validate the Search Analytics search type against the API's accepted set.

    Returns the stripped value, or None when none is supplied. Raises UserInputError naming
    the unsupported value so the caller gets a clear message instead of an opaque 400.
    """
    if search_type is None:
        return None
    name = str(search_type).strip()
    if not name:
        return None
    if name not in VALID_SEARCH_TYPES:
        raise UserInputError(
            f"search_type '{name}' is not supported; valid types are: "
            f"{', '.join(sorted(VALID_SEARCH_TYPES))}"
        )
    return name


def build_search_analytics_body(
    start_date: str,
    end_date: str,
    dimensions: Optional[List[str]] = None,
    row_limit: Optional[int] = None,
    start_row: Optional[int] = None,
    dimension_filter_groups: Optional[List[Dict[str, Any]]] = None,
    search_type: Optional[str] = None,
    aggregation_type: Optional[str] = None,
    data_state: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Build a searchAnalytics.query request body from validated arguments.

    ``start_date``/``end_date`` are required ISO dates (YYYY-MM-DD). Only the fields the
    caller supplied are included, so the API applies its own defaults for the rest.
    """
    body: Dict[str, Any] = {
        "startDate": require_non_empty(start_date, "start_date"),
        "endDate": require_non_empty(end_date, "end_date"),
    }
    validated_dimensions = validate_dimensions(dimensions)
    if validated_dimensions:
        body["dimensions"] = validated_dimensions
    if row_limit is not None:
        body["rowLimit"] = row_limit
    if start_row is not None:
        body["startRow"] = start_row
    if dimension_filter_groups:
        body["dimensionFilterGroups"] = dimension_filter_groups
    validated_search_type = validate_search_type(search_type)
    if validated_search_type:
        body["type"] = validated_search_type
    if aggregation_type:
        body["aggregationType"] = aggregation_type
    if data_state:
        body["dataState"] = data_state
    return body


def format_search_analytics_response(
    response: Dict[str, Any], dimensions: List[str]
) -> Dict[str, Any]:
    """
    Flatten a searchAnalytics.query response into readable row dicts.

    Each API row carries a parallel ``keys`` array (one entry per requested dimension)
    plus clicks/impressions/ctr/position. This maps every key back to its dimension name
    so a caller can read results without tracking the dimension order themselves.
    """
    rows: List[Dict[str, Any]] = []
    for row in response.get("rows", []):
        flat: Dict[str, Any] = {}
        for dimension, key in zip(dimensions, row.get("keys", [])):
            flat[dimension] = key
        flat["clicks"] = row.get("clicks")
        flat["impressions"] = row.get("impressions")
        flat["ctr"] = row.get("ctr")
        flat["position"] = row.get("position")
        rows.append(flat)
    return {
        "dimensions": dimensions,
        "rowCount": len(rows),
        "rows": rows,
        "responseAggregationType": response.get("responseAggregationType"),
    }


_GSC_GRANT_HINT = (
    "This is expected until paul@certiv.ai is a verified owner or user of the target "
    "property in Search Console, AND the webmasters scopes have been consented on the "
    "token. A Search Console 403/permission error almost always means the account has "
    "no access to that property (the property must be owned/verified by the auth'd "
    "user), not that the request was malformed."
)


def summarize_gsc_error(error: HttpError, tool_name: str) -> str:
    """
    Build a readable, Search-Console-aware message for a Google API HttpError.

    Surfaces (does not swallow) 403 permission errors with the property-ownership hint,
    since every Search Console call 403s until paul@certiv.ai is a verified owner/user of
    the property and the webmasters scopes are consented.
    """
    error_details = str(error)
    status = getattr(getattr(error, "resp", None), "status", None)

    if status == 403 and "accessNotConfigured" in error_details:
        enablement = get_api_enablement_message(error_details, "searchconsole")
        if enablement:
            return f"API error in {tool_name}: {enablement}"
        return (
            f"API error in {tool_name}: {error}. The Google Search Console API is not "
            f"enabled for this project. Enable searchconsole.googleapis.com in the "
            f"Google Cloud Console."
        )

    if status == 403:
        return f"Permission denied (403) in {tool_name}: {error}. {_GSC_GRANT_HINT}"

    if status == 401:
        return (
            f"Authentication error (401) in {tool_name}: {error}. The token is missing "
            f"or invalid; re-consent the webmasters scopes."
        )

    if status == 404:
        return (
            f"Not found (404) in {tool_name}: {error}. Check the siteUrl / sitemap "
            f"feedpath and that paul@certiv.ai has access to that property."
        )

    return f"API error in {tool_name}: {error}"


def handle_gsc_errors(tool_name: str):
    """
    Decorator that converts Google API HttpErrors from Search Console tools into readable
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
                message = summarize_gsc_error(error, tool_name)
                logger.error(message, exc_info=True)
                raise Exception(message) from error

        return wrapper

    return decorator
