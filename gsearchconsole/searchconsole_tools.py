"""
Google Search Console MCP Tools

Read and manage Search Console properties via the Search Console API (searchconsole
v1, a.k.a. webmasters v3): list sites, run Search Analytics queries, list/get/submit/
delete sitemaps, and inspect a URL's index status.

Read tools require the webmasters.readonly scope; sitemap submit/delete require the
webmasters scope. Every call 403s until the authenticated Google account is a verified
owner or user of the target property in Search Console; see summarize_gsc_error for the
exact guidance surfaced on 403.
"""

import logging
from typing import Any, Dict, List, Optional

from mcp import Resource

from auth.service_decorator import require_google_service
from core.server import server
from core.utils import UserInputError
from gsearchconsole.searchconsole_helpers import (
    build_search_analytics_body,
    format_search_analytics_response,
    handle_gsc_errors,
    require_feedpath,
    require_site_url,
)

logger = logging.getLogger(__name__)

SEARCHCONSOLE = "searchconsole"
READ = "searchconsole_read"
WRITE = "searchconsole_write"


@server.tool()
@require_google_service(SEARCHCONSOLE, READ)
@handle_gsc_errors("list_search_console_sites")
async def list_search_console_sites(
    service: Resource,
    user_google_email: str,
) -> Dict[str, Any]:
    """
    List the Search Console properties the authenticated user can access.

    Each entry carries ``siteUrl`` (a URL-prefix property like
    "https://www.example.com/" or a Domain property like "sc-domain:example.com") and
    ``permissionLevel``. Use the returned siteUrl for the other tools.

    Args:
        user_google_email: The user's Google email address. Required.

    Returns:
        The sites.list response ({"siteEntry": [...]}), empty if no properties.
    """
    logger.info(f"[list_search_console_sites] Invoked. Email: '{user_google_email}'")
    return service.sites().list().execute()


@server.tool()
@require_google_service(SEARCHCONSOLE, READ)
@handle_gsc_errors("get_site")
async def get_site(
    service: Resource,
    user_google_email: str,
    site_url: str,
) -> Dict[str, Any]:
    """
    Get one Search Console property, including the caller's permission level.

    Args:
        user_google_email: The user's Google email address. Required.
        site_url: The property URL exactly as listed by list_search_console_sites, e.g.
            "https://www.example.com/" or "sc-domain:example.com".

    Returns:
        The site resource ({"siteUrl", "permissionLevel"}).
    """
    logger.info(f"[get_site] Invoked. Email: '{user_google_email}'")
    return service.sites().get(siteUrl=require_site_url(site_url)).execute()


@server.tool()
@require_google_service(SEARCHCONSOLE, READ)
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
    data_state: Optional[str] = None,
    aggregation_type: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Run a Search Console Search Analytics query (clicks/impressions/ctr/position).

    Args:
        user_google_email: The user's Google email address. Required.
        site_url: The property URL exactly as listed by list_search_console_sites.
        start_date: Start date, inclusive, "YYYY-MM-DD". Required.
        end_date: End date, inclusive, "YYYY-MM-DD". Required.
        dimensions: Group-by dimensions. Valid values: query, page, country, device,
            searchAppearance, date. Omit for a single totals row.
        row_limit: Max rows to return (1-25000; GSC caps at 25000). Defaults to GSC's
            own default when omitted.
        start_row: Zero-based row offset for pagination.
        dimension_filter_groups: Optional GSC dimensionFilterGroups, e.g.
            [{"groupType": "and", "filters": [{"dimension": "country",
              "operator": "equals", "expression": "usa"}]}].
        search_type: Search type (sent to GSC as "type"): web, image, video, news,
            discover, or googleNews. Defaults to web when omitted.
        data_state: "final" (default) or "all" to include fresh, not-yet-finalized data.
        aggregation_type: How to aggregate results: auto, byProperty, or byPage.

    Returns:
        {"rowCount", "rows": [{"keys", "clicks", "impressions", "ctr", "position"}],
        "responseAggregationType"}.
    """
    logger.info(f"[query_search_analytics] Invoked. Email: '{user_google_email}'")
    body = build_search_analytics_body(
        start_date=start_date,
        end_date=end_date,
        dimensions=dimensions,
        row_limit=row_limit,
        start_row=start_row,
        dimension_filter_groups=dimension_filter_groups,
        search_type=search_type,
        data_state=data_state,
        aggregation_type=aggregation_type,
    )
    response = (
        service.searchanalytics()
        .query(siteUrl=require_site_url(site_url), body=body)
        .execute()
    )
    return format_search_analytics_response(response)


@server.tool()
@require_google_service(SEARCHCONSOLE, READ)
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
        site_url: The property URL exactly as listed by list_search_console_sites.
        sitemap_index: Optional sitemap-index URL to list only its child sitemaps, e.g.
            "https://www.example.com/sitemapindex.xml".

    Returns:
        The sitemaps.list response ({"sitemap": [...]}).
    """
    logger.info(f"[list_sitemaps] Invoked. Email: '{user_google_email}'")
    return (
        service.sitemaps()
        .list(siteUrl=require_site_url(site_url), sitemapIndex=sitemap_index)
        .execute()
    )


@server.tool()
@require_google_service(SEARCHCONSOLE, READ)
@handle_gsc_errors("get_sitemap")
async def get_sitemap(
    service: Resource,
    user_google_email: str,
    site_url: str,
    feedpath: str,
) -> Dict[str, Any]:
    """
    Get one submitted sitemap's status, contents summary, and last-download time.

    Args:
        user_google_email: The user's Google email address. Required.
        site_url: The property URL exactly as listed by list_search_console_sites.
        feedpath: The full sitemap URL, e.g. "https://www.example.com/sitemap.xml".

    Returns:
        The sitemap resource (path, lastSubmitted, isPending, contents, errors, etc.).
    """
    logger.info(f"[get_sitemap] Invoked. Email: '{user_google_email}'")
    return (
        service.sitemaps()
        .get(siteUrl=require_site_url(site_url), feedpath=require_feedpath(feedpath))
        .execute()
    )


@server.tool()
@require_google_service(SEARCHCONSOLE, READ)
@handle_gsc_errors("inspect_url")
async def inspect_url(
    service: Resource,
    user_google_email: str,
    site_url: str,
    inspection_url: str,
    language_code: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Inspect a URL's index status in Search Console (URL Inspection API).

    Args:
        user_google_email: The user's Google email address. Required.
        site_url: The property URL exactly as listed by list_search_console_sites; the
            inspection_url must fall under this property.
        inspection_url: The fully-qualified URL to inspect, e.g.
            "https://www.example.com/some/page".
        language_code: Optional BCP-47 language code for the returned messages, e.g.
            "en-US".

    Returns:
        The urlInspection.index.inspect response ({"inspectionResult": {...}}) with
        index status, coverage, and last-crawl details.
    """
    logger.info(f"[inspect_url] Invoked. Email: '{user_google_email}'")
    inspection = str(inspection_url or "").strip()
    if not inspection:
        raise UserInputError("inspection_url is required")
    body: Dict[str, Any] = {
        "inspectionUrl": inspection,
        "siteUrl": require_site_url(site_url),
    }
    if language_code:
        body["languageCode"] = language_code
    return service.urlInspection().index().inspect(body=body).execute()


@server.tool()
@require_google_service(SEARCHCONSOLE, WRITE)
@handle_gsc_errors("submit_sitemap")
async def submit_sitemap(
    service: Resource,
    user_google_email: str,
    site_url: str,
    feedpath: str,
) -> Dict[str, Any]:
    """
    Submit (or resubmit) a sitemap for a Search Console property.

    Requires the webmasters (write) scope. GSC returns no body on success, so this
    returns a small confirmation dict.

    Args:
        user_google_email: The user's Google email address. Required.
        site_url: The property URL exactly as listed by list_search_console_sites.
        feedpath: The full sitemap URL to submit, e.g.
            "https://www.example.com/sitemap.xml".

    Returns:
        {"status": "submitted", "siteUrl", "feedpath"} on success.
    """
    logger.info(f"[submit_sitemap] Invoked. Email: '{user_google_email}'")
    site = require_site_url(site_url)
    path = require_feedpath(feedpath)
    service.sitemaps().submit(siteUrl=site, feedpath=path).execute()
    return {"status": "submitted", "siteUrl": site, "feedpath": path}


@server.tool()
@require_google_service(SEARCHCONSOLE, WRITE)
@handle_gsc_errors("delete_sitemap")
async def delete_sitemap(
    service: Resource,
    user_google_email: str,
    site_url: str,
    feedpath: str,
) -> Dict[str, Any]:
    """
    Delete (unsubmit) a sitemap from a Search Console property.

    Requires the webmasters (write) scope. GSC returns no body on success, so this
    returns a small confirmation dict.

    Args:
        user_google_email: The user's Google email address. Required.
        site_url: The property URL exactly as listed by list_search_console_sites.
        feedpath: The full sitemap URL to delete, e.g.
            "https://www.example.com/sitemap.xml".

    Returns:
        {"status": "deleted", "siteUrl", "feedpath"} on success.
    """
    logger.info(f"[delete_sitemap] Invoked. Email: '{user_google_email}'")
    site = require_site_url(site_url)
    path = require_feedpath(feedpath)
    service.sitemaps().delete(siteUrl=site, feedpath=path).execute()
    return {"status": "deleted", "siteUrl": site, "feedpath": path}
