"""
Google Workspace Alert Center Read Tools

Read / triage side of the Alert Center, backed by the Alert Center API (alertcenter
v1beta1). Use these to list and inspect admin security alerts (spike in user-reported
spam, suspicious login, phishing reported, etc.), read the feedback left on an alert, and
fetch an alert's metadata.

All tools require the apps.alerts scope (there is no separate readonly scope published by
Google, so the read tools declare a logical read scope that the full apps.alerts scope
covers). Every call 403s until paul@certiv.ai is a Google Workspace admin with Alert
Center privileges and the apps.alerts scope is consented; see
summarize_alert_center_error for the exact guidance surfaced on 403.
"""

import logging
from typing import Any, Dict, Optional

from mcp import Resource

from auth.service_decorator import require_google_service
from core.server import server
from galertcenter.alertcenter_helpers import (
    build_alerts_filter,
    format_alerts_list,
    handle_alert_center_errors,
    require_non_empty,
)

logger = logging.getLogger(__name__)

ALERT_CENTER = "alertcenter"
READ = "alertcenter_read"


@server.tool()
@require_google_service(ALERT_CENTER, READ)
@handle_alert_center_errors("list_alerts")
async def list_alerts(
    service: Resource,
    user_google_email: str,
    alert_type: Optional[str] = None,
    source: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    filter: Optional[str] = None,
    order_by: Optional[str] = None,
    page_size: int = 50,
    page_token: Optional[str] = None,
    customer_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    List Alert Center alerts for the Google Workspace account, newest useful first.

    Args:
        user_google_email: The user's Google email address. Required.
        alert_type: Filter to a single alert type, e.g. "Suspicious login",
            "User reported phishing", "Spike in user-reported spam".
        source: Filter to a single alert source, e.g. "Google" or "Google Workspace".
        start_time: Lower bound on the alert createTime (RFC3339, e.g.
            "2024-01-01T00:00:00Z").
        end_time: Upper bound on the alert createTime (RFC3339).
        filter: Raw Alert Center filter string. When provided it is used verbatim and the
            alert_type/source/start_time/end_time shortcuts are ignored.
        order_by: Sort order, e.g. "create_time desc" (the API default) or
            "create_time asc".
        page_size: Max alerts to return (default 50). The API caps this at 1000.
        page_token: Page token from a previous response for pagination.
        customer_id: Optional Google Workspace customer id; defaults to the account of the
            authenticated admin when omitted.

    Returns:
        {"rowCount", "alerts": [summary, ...], "nextPageToken"} where each summary carries
        alertId, type, source, severity, status, createTime, startTime, endTime, deleted,
        and a compact dataSummary.
    """
    logger.info(f"[list_alerts] Invoked. Email: '{user_google_email}'")
    effective_filter = filter or build_alerts_filter(
        alert_type=alert_type,
        source=source,
        start_time=start_time,
        end_time=end_time,
    )
    request_args: Dict[str, Any] = {"pageSize": page_size}
    if effective_filter:
        request_args["filter"] = effective_filter
    if order_by:
        request_args["orderBy"] = order_by
    if page_token:
        request_args["pageToken"] = page_token
    if customer_id:
        request_args["customerId"] = customer_id

    response = service.alerts().list(**request_args).execute()
    return format_alerts_list(response)


@server.tool()
@require_google_service(ALERT_CENTER, READ)
@handle_alert_center_errors("get_alert")
async def get_alert(
    service: Resource,
    user_google_email: str,
    alert_id: str,
    customer_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Get the full Alert resource for a single alert by id.

    Args:
        user_google_email: The user's Google email address. Required.
        alert_id: The alertId (from list_alerts).
        customer_id: Optional Google Workspace customer id; defaults to the authenticated
            admin's account when omitted.

    Returns:
        The full Alert resource, including its data payload and metadata.
    """
    logger.info(f"[get_alert] Invoked. Email: '{user_google_email}'")
    alert = require_non_empty(alert_id, "alert_id")
    request_args: Dict[str, Any] = {"alertId": alert}
    if customer_id:
        request_args["customerId"] = customer_id
    return service.alerts().get(**request_args).execute()


@server.tool()
@require_google_service(ALERT_CENTER, READ)
@handle_alert_center_errors("get_alert_metadata")
async def get_alert_metadata(
    service: Resource,
    user_google_email: str,
    alert_id: str,
    customer_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Get the metadata for a single alert (severity, status, assignee, etc.).

    Args:
        user_google_email: The user's Google email address. Required.
        alert_id: The alertId (from list_alerts).
        customer_id: Optional Google Workspace customer id; defaults to the authenticated
            admin's account when omitted.

    Returns:
        The AlertMetadata resource for the alert.
    """
    logger.info(f"[get_alert_metadata] Invoked. Email: '{user_google_email}'")
    alert = require_non_empty(alert_id, "alert_id")
    request_args: Dict[str, Any] = {"alertId": alert}
    if customer_id:
        request_args["customerId"] = customer_id
    return service.alerts().getMetadata(**request_args).execute()


@server.tool()
@require_google_service(ALERT_CENTER, READ)
@handle_alert_center_errors("list_alert_feedback")
async def list_alert_feedback(
    service: Resource,
    user_google_email: str,
    alert_id: str,
    filter: Optional[str] = None,
    customer_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    List the feedback entries left on a single alert.

    Args:
        user_google_email: The user's Google email address. Required.
        alert_id: The alertId (from list_alerts).
        filter: Optional Alert Center filter string over the feedback collection.
        customer_id: Optional Google Workspace customer id; defaults to the authenticated
            admin's account when omitted.

    Returns:
        The feedback.list response ({"feedback": [{"feedbackId", "type", ...}, ...]}).
    """
    logger.info(f"[list_alert_feedback] Invoked. Email: '{user_google_email}'")
    alert = require_non_empty(alert_id, "alert_id")
    request_args: Dict[str, Any] = {"alertId": alert}
    if filter:
        request_args["filter"] = filter
    if customer_id:
        request_args["customerId"] = customer_id
    return service.alerts().feedback().list(**request_args).execute()
