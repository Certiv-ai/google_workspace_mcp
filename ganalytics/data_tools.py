"""
Google Analytics 4 Data API MCP Tools

Read / verify side of GA4, backed by the Analytics Data API (analyticsdata v1beta).
Use run_report for historical reporting and run_realtime_report to confirm that
freshly-instrumented events are landing within the last 30 minutes.

All tools require the analytics.readonly scope. Every call 403s until paul@certiv.ai is
granted (at least) Viewer on the target GA4 property and the GA scopes are consented via
bootstrap_auth.py; see summarize_ga_error for the exact guidance surfaced on 403.
"""

import logging
from typing import Any, Dict, List, Optional

from mcp import Resource

from auth.service_decorator import require_google_service
from core.server import server
from ganalytics.analytics_helpers import (
    build_date_ranges,
    build_named_objects,
    format_report_response,
    handle_ga_errors,
    normalize_property_id,
)

logger = logging.getLogger(__name__)

DATA = "analyticsdata"
READ = "analytics_read"


@server.tool()
@require_google_service(DATA, READ)
@handle_ga_errors("run_report", DATA)
async def run_report(
    service: Resource,
    user_google_email: str,
    property_id: str,
    dimensions: Optional[List[str]] = None,
    metrics: Optional[List[str]] = None,
    date_ranges: Optional[List[Dict[str, str]]] = None,
    dimension_filter: Optional[Dict[str, Any]] = None,
    metric_filter: Optional[Dict[str, Any]] = None,
    order_bys: Optional[List[Dict[str, Any]]] = None,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
    keep_empty_rows: bool = False,
) -> Dict[str, Any]:
    """
    Run a GA4 Data API report over a date range.

    Args:
        user_google_email: The user's Google email address. Required.
        property_id: GA4 property id ("123456789") or resource name.
        dimensions: Dimension API names, e.g. ["date", "eventName", "pagePath"].
        metrics: Metric API names, e.g. ["eventCount", "activeUsers", "sessions"].
        date_ranges: List of {"startDate", "endDate"[, "name"]}. Dates accept ISO
            ("2024-01-01") or relative ("7daysAgo", "yesterday", "today") values.
            Defaults to the last 28 days when omitted.
        dimension_filter: Optional FilterExpression applied to dimensions (GA4 shape),
            e.g. {"filter": {"fieldName": "eventName",
                             "stringFilter": {"value": "purchase"}}}.
        metric_filter: Optional FilterExpression applied to metrics.
        order_bys: Optional list of OrderBy objects,
            e.g. [{"metric": {"metricName": "eventCount"}, "desc": true}].
        limit: Max rows to return.
        offset: Row offset for pagination.
        keep_empty_rows: If True, include rows with all-zero metrics.

    Returns:
        A flattened report: {"dimensionHeaders", "metricHeaders", "rowCount", "rows"}.
    """
    logger.info(f"[run_report] Invoked. Email: '{user_google_email}'")
    body: Dict[str, Any] = {
        "dimensions": build_named_objects(dimensions, "dimensions"),
        "metrics": build_named_objects(metrics, "metrics"),
        "dateRanges": build_date_ranges(date_ranges),
        "keepEmptyRows": keep_empty_rows,
    }
    if dimension_filter:
        body["dimensionFilter"] = dimension_filter
    if metric_filter:
        body["metricFilter"] = metric_filter
    if order_bys:
        body["orderBys"] = order_bys
    if limit is not None:
        body["limit"] = limit
    if offset is not None:
        body["offset"] = offset

    response = (
        service.properties()
        .runReport(property=normalize_property_id(property_id), body=body)
        .execute()
    )
    return format_report_response(response)


@server.tool()
@require_google_service(DATA, READ)
@handle_ga_errors("run_realtime_report", DATA)
async def run_realtime_report(
    service: Resource,
    user_google_email: str,
    property_id: str,
    dimensions: Optional[List[str]] = None,
    metrics: Optional[List[str]] = None,
    dimension_filter: Optional[Dict[str, Any]] = None,
    metric_filter: Optional[Dict[str, Any]] = None,
    order_bys: Optional[List[Dict[str, Any]]] = None,
    limit: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Run a GA4 realtime report over roughly the last 30 minutes of activity.

    Use this to confirm that a freshly-instrumented event is actually landing right after
    tagging, without waiting for standard reporting to process.

    Args:
        user_google_email: The user's Google email address. Required.
        property_id: GA4 property id ("123456789") or resource name.
        dimensions: Realtime dimension API names, e.g. ["eventName", "unifiedScreenName"].
        metrics: Realtime metric API names, e.g. ["eventCount", "activeUsers"].
        dimension_filter: Optional FilterExpression applied to dimensions.
        metric_filter: Optional FilterExpression applied to metrics.
        order_bys: Optional list of OrderBy objects.
        limit: Max rows to return.

    Returns:
        A flattened report: {"dimensionHeaders", "metricHeaders", "rowCount", "rows"}.
    """
    logger.info(f"[run_realtime_report] Invoked. Email: '{user_google_email}'")
    body: Dict[str, Any] = {
        "dimensions": build_named_objects(dimensions, "dimensions"),
        "metrics": build_named_objects(metrics, "metrics"),
    }
    if dimension_filter:
        body["dimensionFilter"] = dimension_filter
    if metric_filter:
        body["metricFilter"] = metric_filter
    if order_bys:
        body["orderBys"] = order_bys
    if limit is not None:
        body["limit"] = limit

    response = (
        service.properties()
        .runRealtimeReport(property=normalize_property_id(property_id), body=body)
        .execute()
    )
    return format_report_response(response)
