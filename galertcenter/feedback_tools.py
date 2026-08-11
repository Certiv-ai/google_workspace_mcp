"""
Google Workspace Alert Center Feedback Tools

Feedback side of the Alert Center, backed by the Alert Center API (alertcenter v1beta1).
create_alert_feedback marks an alert useful or not useful; this is the non-destructive way
to triage an alert as benign or actionable (it never deletes, undeletes, or hides alerts).

This tool requires the full apps.alerts scope. Every call 403s until paul@certiv.ai is a
Google Workspace admin with Alert Center privileges and the apps.alerts scope is
consented; see summarize_alert_center_error for the exact guidance surfaced on 403.
"""

import logging
from typing import Any, Dict

from mcp import Resource

from auth.service_decorator import require_google_service
from core.server import server
from galertcenter.alertcenter_helpers import (
    build_feedback_body,
    handle_alert_center_errors,
    require_non_empty,
)

logger = logging.getLogger(__name__)

ALERT_CENTER = "alertcenter"
WRITE = "alertcenter"


@server.tool()
@require_google_service(ALERT_CENTER, WRITE)
@handle_alert_center_errors("create_alert_feedback")
async def create_alert_feedback(
    service: Resource,
    user_google_email: str,
    alert_id: str,
    feedback_type: str,
) -> Dict[str, Any]:
    """
    Leave feedback on an alert, marking it useful or not useful (non-destructive triage).

    Args:
        user_google_email: The user's Google email address. Required.
        alert_id: The alertId (from list_alerts).
        feedback_type: One of ALERT_FEEDBACK_TYPE_UNSPECIFIED, NOT_USEFUL,
            SOMEWHAT_USEFUL, VERY_USEFUL. Use NOT_USEFUL to mark an alert benign and
            VERY_USEFUL / SOMEWHAT_USEFUL to mark it actionable.

    Returns:
        The created AlertFeedback resource ({"feedbackId", "type", "createTime", ...}).
    """
    logger.info(f"[create_alert_feedback] Invoked. Email: '{user_google_email}'")
    alert = require_non_empty(alert_id, "alert_id")
    body = build_feedback_body(feedback_type)
    return service.alerts().feedback().create(alertId=alert, body=body).execute()
