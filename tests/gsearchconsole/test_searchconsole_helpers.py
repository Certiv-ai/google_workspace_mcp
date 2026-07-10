"""
Unit tests for the Search Console helper functions.

These cover the pure logic used by the Search Console tools (site-url/feedpath
validation, Search Analytics request shaping, response flattening, and GSC-aware error
summaries) without touching live Search Console, which requires a property grant on the
authenticated account that is documented as a human-only follow-up.
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
    normalize_dimensions,
    require_feedpath,
    require_site_url,
    summarize_gsc_error,
)


def _http_error(status: int, content: bytes = b"{}") -> HttpError:
    return HttpError(
        Response({"status": status, "reason": "x"}), content, uri="https://x"
    )


class TestValidation:
    def test_site_url_passthrough(self):
        assert (
            require_site_url("https://www.example.com/") == "https://www.example.com/"
        )

    def test_site_url_domain_property(self):
        assert require_site_url("sc-domain:example.com") == "sc-domain:example.com"

    def test_site_url_strips_whitespace(self):
        assert require_site_url("  https://x/ ") == "https://x/"

    def test_site_url_empty_raises(self):
        with pytest.raises(UserInputError):
            require_site_url("")

    def test_feedpath_passthrough(self):
        assert require_feedpath("https://x/sitemap.xml") == "https://x/sitemap.xml"

    def test_feedpath_empty_raises(self):
        with pytest.raises(UserInputError):
            require_feedpath("  ")


class TestDimensions:
    def test_none_is_empty(self):
        assert normalize_dimensions(None) == []

    def test_valid_passthrough_and_strip(self):
        assert normalize_dimensions([" query ", "page"]) == ["query", "page"]

    def test_invalid_dimension_raises(self):
        with pytest.raises(UserInputError):
            normalize_dimensions(["query", "bogus"])

    def test_empty_string_raises(self):
        with pytest.raises(UserInputError):
            normalize_dimensions([""])


class TestBuildBody:
    def test_minimal_body(self):
        body = build_search_analytics_body("2024-01-01", "2024-01-31")
        assert body == {"startDate": "2024-01-01", "endDate": "2024-01-31"}

    def test_missing_dates_raises(self):
        with pytest.raises(UserInputError):
            build_search_analytics_body("", "2024-01-31")

    def test_full_body(self):
        body = build_search_analytics_body(
            "2024-01-01",
            "2024-01-31",
            dimensions=["query", "country"],
            row_limit=10,
            start_row=5,
            dimension_filter_groups=[{"filters": []}],
            search_type="web",
            data_state="all",
            aggregation_type="byPage",
        )
        assert body["dimensions"] == ["query", "country"]
        assert body["rowLimit"] == 10
        assert body["startRow"] == 5
        assert body["dimensionFilterGroups"] == [{"filters": []}]
        # search_type maps to the GSC "type" field.
        assert body["type"] == "web"
        assert body["dataState"] == "all"
        assert body["aggregationType"] == "byPage"

    def test_row_limit_capped_at_25000(self):
        body = build_search_analytics_body("2024-01-01", "2024-01-31", row_limit=99999)
        assert body["rowLimit"] == 25000

    def test_row_limit_non_positive_raises(self):
        with pytest.raises(UserInputError):
            build_search_analytics_body("2024-01-01", "2024-01-31", row_limit=0)

    def test_start_row_negative_raises(self):
        with pytest.raises(UserInputError):
            build_search_analytics_body("2024-01-01", "2024-01-31", start_row=-1)

    def test_bad_aggregation_type_raises(self):
        with pytest.raises(UserInputError):
            build_search_analytics_body(
                "2024-01-01", "2024-01-31", aggregation_type="nonsense"
            )


class TestFormatResponse:
    def test_flattens_rows(self):
        response = {
            "rows": [
                {
                    "keys": ["python", "usa"],
                    "clicks": 10.0,
                    "impressions": 100.0,
                    "ctr": 0.1,
                    "position": 3.5,
                }
            ],
            "responseAggregationType": "byProperty",
        }
        result = format_search_analytics_response(response)
        assert result["rowCount"] == 1
        assert result["responseAggregationType"] == "byProperty"
        row = result["rows"][0]
        assert row["keys"] == ["python", "usa"]
        assert row["clicks"] == 10.0
        assert row["position"] == 3.5

    def test_empty_response(self):
        result = format_search_analytics_response({})
        assert result == {"rowCount": 0, "rows": []}


class TestErrorSummary:
    def test_403_surfaces_access_hint(self):
        msg = summarize_gsc_error(_http_error(403), "get_site")
        assert "Permission denied (403)" in msg
        assert "verified owner or user" in msg

    def test_401_mentions_reconsent(self):
        msg = summarize_gsc_error(_http_error(401), "list_sitemaps")
        assert "Authentication error (401)" in msg

    def test_404_mentions_resource(self):
        msg = summarize_gsc_error(_http_error(404), "get_sitemap")
        assert "Not found (404)" in msg

    def test_other_status_generic(self):
        msg = summarize_gsc_error(_http_error(500), "query_search_analytics")
        assert "API error in query_search_analytics" in msg
