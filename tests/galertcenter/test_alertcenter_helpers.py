"""
Unit tests for the Alert Center helper functions.

These cover the pure logic used by the read and feedback tools (filter building, alert
summarization, feedback-body validation, and Alert-Center-aware error summaries) without
touching the live Alert Center API, which requires the admin role and apps.alerts consent
that are documented as human-only follow-ups.
"""

import os
import sys

import pytest
from httplib2 import Response

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from googleapiclient.errors import HttpError  # noqa: E402

from core.utils import UserInputError  # noqa: E402
from galertcenter.alertcenter_helpers import (  # noqa: E402
    build_alerts_filter,
    build_feedback_body,
    format_alerts_list,
    require_non_empty,
    summarize_alert,
    summarize_alert_center_error,
)


def _http_error(status: int, content: bytes = b"{}") -> HttpError:
    return HttpError(
        Response({"status": status, "reason": "x"}), content, uri="https://x"
    )


class TestRequireNonEmpty:
    def test_strips_and_returns(self):
        assert require_non_empty("  abc ", "alert_id") == "abc"

    def test_raises_on_empty(self):
        with pytest.raises(UserInputError):
            require_non_empty("   ", "alert_id")

    def test_raises_on_none(self):
        with pytest.raises(UserInputError):
            require_non_empty(None, "alert_id")


class TestBuildAlertsFilter:
    def test_none_when_no_args(self):
        assert build_alerts_filter() is None

    def test_type_only(self):
        assert build_alerts_filter(alert_type="Suspicious login") == (
            'type = "Suspicious login"'
        )

    def test_all_fields_anded(self):
        result = build_alerts_filter(
            alert_type="Suspicious login",
            source="Google",
            start_time="2024-01-01T00:00:00Z",
            end_time="2024-02-01T00:00:00Z",
        )
        assert result == (
            'type = "Suspicious login" AND source = "Google" AND '
            'createTime >= "2024-01-01T00:00:00Z" AND '
            'createTime <= "2024-02-01T00:00:00Z"'
        )

    def test_blank_values_ignored(self):
        assert build_alerts_filter(alert_type="   ", source="") is None

    def test_embedded_quote_is_escaped(self):
        result = build_alerts_filter(alert_type='a "b" c')
        assert result == 'type = "a \\"b\\" c"'


class TestSummarizeAlert:
    def test_extracts_summary_fields(self):
        alert = {
            "alertId": "a1",
            "customerId": "C123",
            "type": "Suspicious login",
            "source": "Google",
            "createTime": "2024-01-01T00:00:00Z",
            "startTime": "2024-01-01T00:00:00Z",
            "endTime": "2024-01-01T01:00:00Z",
            "metadata": {"severity": "HIGH", "status": "NOT_STARTED"},
            "data": {"@type": "type.googleapis.com/x.LoginDetails", "loginName": "u"},
        }
        summary = summarize_alert(alert)
        assert summary["alertId"] == "a1"
        assert summary["severity"] == "HIGH"
        assert summary["status"] == "NOT_STARTED"
        assert summary["deleted"] is False
        assert summary["dataSummary"]["type"] == "type.googleapis.com/x.LoginDetails"
        assert summary["dataSummary"]["keys"] == ["loginName"]

    def test_missing_metadata_and_data(self):
        summary = summarize_alert({"alertId": "a2"})
        assert summary["severity"] is None
        assert summary["dataSummary"] == {"keys": []}


class TestFormatAlertsList:
    def test_wraps_rows_and_token(self):
        response = {
            "alerts": [{"alertId": "a1"}, {"alertId": "a2"}],
            "nextPageToken": "tok",
        }
        result = format_alerts_list(response)
        assert result["rowCount"] == 2
        assert result["nextPageToken"] == "tok"
        assert [a["alertId"] for a in result["alerts"]] == ["a1", "a2"]

    def test_empty_response(self):
        result = format_alerts_list({})
        assert result["rowCount"] == 0
        assert result["alerts"] == []
        assert result["nextPageToken"] is None


class TestBuildFeedbackBody:
    def test_valid_type(self):
        assert build_feedback_body("VERY_USEFUL") == {"type": "VERY_USEFUL"}

    def test_strips_whitespace(self):
        assert build_feedback_body("  NOT_USEFUL ") == {"type": "NOT_USEFUL"}

    def test_rejects_unknown_type(self):
        with pytest.raises(UserInputError):
            build_feedback_body("MAYBE_USEFUL")

    def test_rejects_empty(self):
        with pytest.raises(UserInputError):
            build_feedback_body("")


class TestSummarizeAlertCenterError:
    def test_403_includes_grant_hint(self):
        message = summarize_alert_center_error(_http_error(403), "list_alerts")
        assert "Permission denied (403)" in message
        assert "apps.alerts" in message

    def test_401_mentions_reconsent(self):
        message = summarize_alert_center_error(_http_error(401), "get_alert")
        assert "Authentication error (401)" in message

    def test_404_mentions_alert_id(self):
        message = summarize_alert_center_error(_http_error(404), "get_alert")
        assert "Not found (404)" in message
        assert "alertId" in message

    def test_403_access_not_configured_uses_enablement(self):
        content = b'{"error": {"message": "accessNotConfigured"}}'
        message = summarize_alert_center_error(_http_error(403, content), "list_alerts")
        assert "Alert Center" in message
