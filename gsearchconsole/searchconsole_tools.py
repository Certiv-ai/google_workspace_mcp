"""
Google Search Console Read Tools

Read / verify side of Search Console, backed by the Search Console API (searchconsole v1).
Use these to discover verified properties, pull search-performance analytics, list
sitemaps, and inspect the index status of a single URL.

All tools require the webmasters.readonly scope. Every call 403s until paul@certiv.ai is a
verified owner/user of the target property and the webmasters scopes are consented; see
summarize_gsc_error for the exact guidance surfaced on 403.
"""

import logging
from typing import Any, Dict, List, Optional

from mcp import Resource

from auth.service_decorator import require_google_service
from core.server import server
from gsearchconsole.searchconsole_helpers import (
    build_search_analytics_body,
    format_search_analytics_response,
    handle_gsc_errors,
    require_non_empty,
)

logger = logging.getLogger(__name__)

SC = "searchconsole"
READ = "searchconsole_read"


@server.tool()
@require_google_service(SC, READ)
@handle_gsc_errors("list_search_console_sites")
async def list_search_console_sites(
    service: Resource,
    user_google_email: str,
) -> Dict[str, Any]:
    """
    List the Search Console sites (properties) the authenticated user can access.

    Each entry carries the ``siteUrl`` (e.g. "https://example.com/" or a
    "sc-domain:example.com" domain property) and the user's permission level for it, so
    this is the fastest way to discover the siteUrl values the other tools need.

    Args:
        user_google_email: The user's Google email address. Required.

    Returns:
        The sites.list response ({"siteEntry": [{"siteUrl", "permissionLevel"}, ...]}).
    """
    logger.info(f"[list_search_console_sites] Invoked. Email: '{user_google_email}'")
    return service.sites().list().execute()


@server.tool()
@require_google_service(SC, READ)
@handle_gsc_errors("get_site")
async def get_site(
    service: Resource,
    user_google_email: str,
    site_url: str,
) -> Dict[str, Any]:
    """
    Get a single Search Console site's details, including the user's permission level.

    Args:
        user_google_email: The user's Google email address. Required.
        site_url: The property, exactly as it appears in Search Console, e.g.
            "https://example.com/" (URL-prefix) or "sc-domain:example.com" (domain).

    Returns:
        The sites.get response ({"siteUrl", "permissionLevel"}).
    """
    logger.info(f"[get_site] Invoked. Email: '{user_google_email}'")
    site = require_non_empty(site_url, "site_url")
    return service.sites().get(siteUrl=site).execute()


@server.tool()
@require_google_service(SC, READ)
@handle_gsc_errors("query_search_analytics")
async def query_search_analytics(
    service: Resource,
    user_google_email: str,
    site_url: str,
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
    Query Search Console search-performance analytics for a property and date range.

    Args:
        user_google_email: The user's Google email address. Required.
        site_url: The property, e.g. "https://example.com/" or "sc-domain:example.com".
        start_date: Start date, inclusive, as ISO "YYYY-MM-DD".
        end_date: End date, inclusive, as ISO "YYYY-MM-DD".
        dimensions: Optional group-by dimensions; any of "query", "page", "country",
            "device", "searchAppearance", "date". Omit for site-wide totals.
        row_limit: Max rows to return (API default 1000, max 25000).
        start_row: Zero-based row offset for pagination.
        dimension_filter_groups: Optional list of FilterGroup objects, e.g.
            [{"filters": [{"dimension": "country", "operator": "equals",
                           "expression": "usa"}]}].
        search_type: Optional result type; one of "web", "image", "video", "news",
            "discover", "googleNews" (API field "type").
        aggregation_type: Optional "auto", "byPage", or "byProperty".
        data_state: Optional data freshness: "full" (finalized data only) or "all"
            (include fresh, still-being-processed data). Omit to use the API default.

    Returns:
        Flattened analytics: {"dimensions", "rowCount", "rows", "responseAggregationType"}
        where each row maps every requested dimension to its key plus clicks, impressions,
        ctr, and position.
    """
    logger.info(f"[query_search_analytics] Invoked. Email: '{user_google_email}'")
    site = require_non_empty(site_url, "site_url")
    body = build_search_analytics_body(
        start_date=start_date,
        end_date=end_date,
        dimensions=dimensions,
        row_limit=row_limit,
        start_row=start_row,
        dimension_filter_groups=dimension_filter_groups,
        search_type=search_type,
        aggregation_type=aggregation_type,
        data_state=data_state,
    )
    response = service.searchanalytics().query(siteUrl=site, body=body).execute()
    # body["dimensions"] is the already-validated list (or absent for site-wide totals);
    # reuse it so validation runs exactly once, in build_search_analytics_body.
    return format_search_analytics_response(response, body.get("dimensions", []))


@server.tool()
@require_google_service(SC, READ)
@handle_gsc_errors("list_sitemaps")
async def list_sitemaps(
    service: Resource,
    user_google_email: str,
    site_url: str,
    sitemap_index: Optional[str] = None,
) -> Dict[str, Any]:
    """
    List the sitemaps submitted for a Search Console property.

    Args:
        user_google_email: The user's Google email address. Required.
        site_url: The property, e.g. "https://example.com/" or "sc-domain:example.com".
        sitemap_index: Optional full URL of a sitemap-index file; when given, lists only
            the sitemaps contained in that index.

    Returns:
        The sitemaps.list response ({"sitemap": [{"path", "lastSubmitted", ...}, ...]}).
    """
    logger.info(f"[list_sitemaps] Invoked. Email: '{user_google_email}'")
    site = require_non_empty(site_url, "site_url")
    request = service.sitemaps().list(siteUrl=site, sitemapIndex=sitemap_index)
    return request.execute()


@server.tool()
@require_google_service(SC, READ)
@handle_gsc_errors("get_sitemap")
async def get_sitemap(
    service: Resource,
    user_google_email: str,
    site_url: str,
    feedpath: str,
) -> Dict[str, Any]:
    """
    Get details for a single submitted sitemap, including its processing status.

    Args:
        user_google_email: The user's Google email address. Required.
        site_url: The property, e.g. "https://example.com/" or "sc-domain:example.com".
        feedpath: The full URL of the sitemap, e.g. "https://example.com/sitemap.xml".

    Returns:
        The sitemaps.get response ({"path", "lastSubmitted", "contents", "errors", ...}).
    """
    logger.info(f"[get_sitemap] Invoked. Email: '{user_google_email}'")
    site = require_non_empty(site_url, "site_url")
    path = require_non_empty(feedpath, "feedpath")
    return service.sitemaps().get(siteUrl=site, feedpath=path).execute()


@server.tool()
@require_google_service(SC, READ)
@handle_gsc_errors("inspect_url")
async def inspect_url(
    service: Resource,
    user_google_email: str,
    inspection_url: str,
    site_url: str,
    language_code: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Inspect a single URL's index status via the URL Inspection API.

    Args:
        user_google_email: The user's Google email address. Required.
        inspection_url: The fully-qualified URL to inspect. Must belong to the property
            given by ``site_url``.
        site_url: The property that owns the URL, e.g. "https://example.com/" or
            "sc-domain:example.com".
        language_code: Optional BCP-47 language code for the returned messages
            (e.g. "en-US"); defaults to the API's own default when omitted.

    Returns:
        The urlInspection.index.inspect response ({"inspectionResult": {...}}) with the
        index status, coverage, and any detected issues.
    """
    logger.info(f"[inspect_url] Invoked. Email: '{user_google_email}'")
    body: Dict[str, Any] = {
        "inspectionUrl": require_non_empty(inspection_url, "inspection_url"),
        "siteUrl": require_non_empty(site_url, "site_url"),
    }
    if language_code:
        body["languageCode"] = language_code
    return service.urlInspection().index().inspect(body=body).execute()
