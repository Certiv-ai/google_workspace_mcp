"""
Google Workspace Alert Center Feedback Tools

Feedback side of the Alert Center, backed by the Alert Center API (alertcenter v1beta1).
create_alert_feedback records whether an alert report was useful. It is non-destructive
and, importantly, does NOT triage or resolve the alert: it never changes the alert's
status, assignee, or visibility, and never deletes/undeletes/hides alerts. It only signals
alert quality back to Google.

This tool requires the full apps.alerts scope. Every call 403s until paul@certiv.ai is a
Google Workspace admin with Alert Center privileges and the apps.alerts scope is
consented; see summarize_alert_center_error for the exact guidance surfaced on 403.
"""

import logging
from typing import Any

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
) -> dict[str, Any]:
    """
    Rate how useful an alert was (non-destructive; does NOT triage or close the alert).

    This records feedback on the alert report's quality only. It does not change the
    alert's status, assignee, or visibility and does not resolve/close it; use the Alert
    Center console (or a dedicated status update) for actual triage.

    Args:
        user_google_email: The user's Google email address. Required.
        alert_id: The alertId (from list_alerts).
        feedback_type: One of ALERT_FEEDBACK_TYPE_UNSPECIFIED, NOT_USEFUL,
            SOMEWHAT_USEFUL, VERY_USEFUL. NOT_USEFUL flags a low-value / false-positive
            alert; VERY_USEFUL / SOMEWHAT_USEFUL flag a valuable one.

    Returns:
        The created AlertFeedback resource ({"feedbackId", "type", "createTime", ...}).
    """
    logger.info(f"[create_alert_feedback] Invoked. Email: '{user_google_email}'")
    alert = require_non_empty(alert_id, "alert_id")
    body = build_feedback_body(feedback_type)
    return service.alerts().feedback().create(alertId=alert, body=body).execute()
