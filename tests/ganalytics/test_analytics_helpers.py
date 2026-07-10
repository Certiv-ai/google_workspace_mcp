"""
Unit tests for the GA4 helper functions.

These cover the pure logic used by the Admin and Data API tools (resource-name
normalization, report request/response shaping, and GA-aware error summaries) without
touching live Google Analytics, which requires the property grant and re-consent that
are documented as human-only follow-ups.
"""

import os
import sys

import pytest
from httplib2 import Response

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from googleapiclient.errors import HttpError  # noqa: E402

from core.utils import UserInputError  # noqa: E402
from ganalytics.analytics_helpers import (  # noqa: E402
    build_date_ranges,
    build_named_objects,
    format_report_response,
    normalize_account_id,
    normalize_data_stream_name,
    normalize_property_id,
    require_fields,
    summarize_ga_error,
)


def _http_error(status: int, content: bytes = b"{}") -> HttpError:
    return HttpError(Response({"status": status, "reason": "x"}), content, uri="https://x")


class TestNormalization:
    def test_property_id_bare(self):
        assert normalize_property_id("123456789") == "properties/123456789"

    def test_property_id_already_qualified(self):
        assert normalize_property_id("properties/123") == "properties/123"

    def test_property_id_strips_whitespace(self):
        assert normalize_property_id("  42 ") == "properties/42"

    def test_property_id_empty_raises(self):
        with pytest.raises(UserInputError):
            normalize_property_id("")

    def test_account_id_bare_and_qualified(self):
        assert normalize_account_id("7") == "accounts/7"
        assert normalize_account_id("accounts/7") == "accounts/7"

    def test_data_stream_from_bare_id(self):
        assert (
            normalize_data_stream_name("123", "456")
            == "properties/123/dataStreams/456"
        )

    def test_data_stream_from_full_name(self):
        full = "properties/123/dataStreams/456"
        assert normalize_data_stream_name("ignored", full) == full

    def test_data_stream_empty_raises(self):
        with pytest.raises(UserInputError):
            normalize_data_stream_name("123", "")


class TestDateRanges:
    def test_default_is_last_28_days(self):
        assert build_date_ranges(None) == [
            {"startDate": "28daysAgo", "endDate": "today"}
        ]

    def test_passthrough_with_name(self):
        result = build_date_ranges(
            [{"startDate": "2024-01-01", "endDate": "2024-01-31", "name": "jan"}]
        )
        assert result == [
            {"startDate": "2024-01-01", "endDate": "2024-01-31", "name": "jan"}
        ]

    def test_snake_case_aliases_accepted(self):
        result = build_date_ranges([{"start_date": "7daysAgo", "end_date": "today"}])
        assert result == [{"startDate": "7daysAgo", "endDate": "today"}]

    def test_missing_end_date_raises(self):
        with pytest.raises(UserInputError):
            build_date_ranges([{"startDate": "7daysAgo"}])

    def test_non_dict_entry_raises(self):
        with pytest.raises(UserInputError):
            build_date_ranges(["2024-01-01"])


class TestNamedObjects:
    def test_builds_name_objects(self):
        assert build_named_objects(["date", "eventName"], "dimensions") == [
            {"name": "date"},
            {"name": "eventName"},
        ]

    def test_empty_returns_empty_list(self):
        assert build_named_objects(None, "metrics") == []

    def test_blank_entry_raises(self):
        with pytest.raises(UserInputError):
            build_named_objects(["ok", "  "], "metrics")


class TestFormatReportResponse:
    def test_flattens_rows(self):
        response = {
            "dimensionHeaders": [{"name": "eventName"}],
            "metricHeaders": [{"name": "eventCount"}],
            "rows": [
                {
                    "dimensionValues": [{"value": "purchase"}],
                    "metricValues": [{"value": "42"}],
                }
            ],
            "rowCount": 1,
        }
        result = format_report_response(response)
        assert result["rows"] == [{"eventName": "purchase", "eventCount": "42"}]
        assert result["dimensionHeaders"] == ["eventName"]
        assert result["metricHeaders"] == ["eventCount"]
        assert result["rowCount"] == 1

    def test_empty_response(self):
        result = format_report_response({})
        assert result["rows"] == []
        assert result["rowCount"] == 0

    def test_preserves_totals_and_metadata(self):
        response = {"totals": [{"metricValues": [{"value": "9"}]}], "metadata": {"x": 1}}
        result = format_report_response(response)
        assert result["totals"] == response["totals"]
        assert result["metadata"] == response["metadata"]


class TestRequireFields:
    def test_passes_when_present(self):
        require_fields({"a": 1, "b": 2}, ["a", "b"], "thing")

    def test_raises_listing_missing(self):
        with pytest.raises(UserInputError) as exc:
            require_fields({"a": 1}, ["a", "b"], "thing")
        assert "b" in str(exc.value)


class TestSummarizeGaError:
    def test_403_surfaces_property_grant_hint(self):
        msg = summarize_ga_error(_http_error(403), "run_report", "analyticsdata")
        assert "Permission denied (403)" in msg
        assert "granted a role" in msg

    def test_403_access_not_configured_gives_enable_link(self):
        msg = summarize_ga_error(
            _http_error(403, b"accessNotConfigured analyticsdata"),
            "run_report",
            "analyticsdata",
        )
        assert "enableapi" in msg

    def test_401_suggests_reconsent(self):
        msg = summarize_ga_error(_http_error(401), "run_report", "analyticsdata")
        assert "401" in msg and "bootstrap_auth.py" in msg

    def test_404_is_readable(self):
        msg = summarize_ga_error(_http_error(404), "get_property", "analyticsadmin")
        assert "Not found (404)" in msg

    def test_other_status_falls_through(self):
        msg = summarize_ga_error(_http_error(400), "run_report", "analyticsdata")
        assert "API error in run_report" in msg
