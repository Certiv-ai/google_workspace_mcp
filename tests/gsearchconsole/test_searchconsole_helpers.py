"""
Unit tests for the Search Console helper functions.

These cover the pure logic used by the read and sitemap-write tools (argument validation,
search-analytics request/response shaping, and Search-Console-aware error summaries)
without touching live Search Console, which requires the property grant and re-consent
that are documented as human-only follow-ups.
"""

import os
import sys

import pytest
from httplib2 import Response

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from googleapiclient.errors import HttpError  # noqa: E402

from core.utils import UserInputError  # noqa: E402
from gsearchconsole.searchconsole_helpers import (  # noqa: E402
    build_search_analytics_body,
    format_search_analytics_response,
    require_non_empty,
    summarize_gsc_error,
    validate_dimensions,
)


def _http_error(status: int, content: bytes = b"{}") -> HttpError:
    return HttpError(
        Response({"status": status, "reason": "x"}), content, uri="https://x"
    )


class TestRequireNonEmpty:
    def test_strips_and_returns(self):
        assert require_non_empty("  https://x/ ", "site_url") == "https://x/"

    def test_empty_raises(self):
        with pytest.raises(UserInputError):
            require_non_empty("", "site_url")


class TestValidateDimensions:
    def test_none_is_empty(self):
        assert validate_dimensions(None) == []

    def test_valid_passthrough(self):
        assert validate_dimensions(["query", "page"]) == ["query", "page"]

    def test_unknown_dimension_raises(self):
        with pytest.raises(UserInputError):
            validate_dimensions(["query", "bogus"])

    def test_blank_dimension_raises(self):
        with pytest.raises(UserInputError):
            validate_dimensions(["  "])


class TestBuildSearchAnalyticsBody:
    def test_minimal_body(self):
        body = build_search_analytics_body("2024-01-01", "2024-01-31")
        assert body == {"startDate": "2024-01-01", "endDate": "2024-01-31"}

    def test_missing_start_raises(self):
        with pytest.raises(UserInputError):
            build_search_analytics_body("", "2024-01-31")

    def test_full_body_only_includes_supplied_fields(self):
        body = build_search_analytics_body(
            "2024-01-01",
            "2024-01-31",
            dimensions=["query"],
            row_limit=50,
            start_row=10,
            dimension_filter_groups=[{"filters": []}],
            search_type="web",
            aggregation_type="byPage",
            data_state="all",
        )
        assert body["dimensions"] == ["query"]
        assert body["rowLimit"] == 50
        assert body["startRow"] == 10
        assert body["dimensionFilterGroups"] == [{"filters": []}]
        assert body["type"] == "web"
        assert body["aggregationType"] == "byPage"
        assert body["dataState"] == "all"

    def test_invalid_dimension_raises(self):
        with pytest.raises(UserInputError):
            build_search_analytics_body("2024-01-01", "2024-01-31", dimensions=["nope"])


class TestFormatSearchAnalyticsResponse:
    def test_flattens_rows_with_dimensions(self):
        response = {
            "rows": [
                {
                    "keys": ["shoes", "USA"],
                    "clicks": 10,
                    "impressions": 100,
                    "ctr": 0.1,
                    "position": 3.5,
                }
            ],
            "responseAggregationType": "byProperty",
        }
        result = format_search_analytics_response(response, ["query", "country"])
        assert result["rows"] == [
            {
                "query": "shoes",
                "country": "USA",
                "clicks": 10,
                "impressions": 100,
                "ctr": 0.1,
                "position": 3.5,
            }
        ]
        assert result["rowCount"] == 1
        assert result["dimensions"] == ["query", "country"]
        assert result["responseAggregationType"] == "byProperty"

    def test_no_dimensions_totals_row(self):
        response = {
            "rows": [{"clicks": 5, "impressions": 50, "ctr": 0.1, "position": 2}]
        }
        result = format_search_analytics_response(response, [])
        assert result["rows"] == [
            {"clicks": 5, "impressions": 50, "ctr": 0.1, "position": 2}
        ]

    def test_empty_response(self):
        result = format_search_analytics_response({}, ["query"])
        assert result["rows"] == []
        assert result["rowCount"] == 0


class TestSummarizeGscError:
    def test_403_surfaces_property_ownership_hint(self):
        msg = summarize_gsc_error(_http_error(403), "query_search_analytics")
        assert "Permission denied (403)" in msg
        assert "verified owner" in msg

    def test_403_access_not_configured_gives_enable_link(self):
        msg = summarize_gsc_error(
            _http_error(403, b"accessNotConfigured searchconsole"),
            "query_search_analytics",
        )
        assert "enableapi" in msg

    def test_401_suggests_reconsent(self):
        msg = summarize_gsc_error(_http_error(401), "list_search_console_sites")
        assert "401" in msg and "webmasters" in msg

    def test_404_is_readable(self):
        msg = summarize_gsc_error(_http_error(404), "get_sitemap")
        assert "Not found (404)" in msg

    def test_other_status_falls_through(self):
        msg = summarize_gsc_error(_http_error(400), "submit_sitemap")
        assert "API error in submit_sitemap" in msg
