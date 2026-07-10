"""
Google Search Console Sitemap Write Tools

Write side of Search Console, backed by the Search Console API (searchconsole v1). These
submit or delete a sitemap for a property.

Both tools require the full webmasters scope. Every call 403s until paul@certiv.ai is a
verified owner/user of the target property and the webmasters scope is consented; see
summarize_gsc_error for the exact guidance surfaced on 403.
"""

import logging
from typing import Any, Dict

from mcp import Resource

from auth.service_decorator import require_google_service
from gsearchconsole.searchconsole_helpers import handle_gsc_errors, require_non_empty
from core.server import server

logger = logging.getLogger(__name__)

SC = "searchconsole"
WRITE = "searchconsole"


@server.tool()
@require_google_service(SC, WRITE)
@handle_gsc_errors("submit_sitemap")
async def submit_sitemap(
    service: Resource,
    user_google_email: str,
    site_url: str,
    feedpath: str,
) -> Dict[str, Any]:
    """
    Submit (or resubmit) a sitemap for a Search Console property.

    Args:
        user_google_email: The user's Google email address. Required.
        site_url: The property, e.g. "https://example.com/" or "sc-domain:example.com".
        feedpath: The full URL of the sitemap to submit, e.g.
            "https://example.com/sitemap.xml".

    Returns:
        A confirmation dict; the API returns an empty body on success.
    """
    logger.info(f"[submit_sitemap] Invoked. Email: '{user_google_email}'")
    site = require_non_empty(site_url, "site_url")
    path = require_non_empty(feedpath, "feedpath")
    service.sitemaps().submit(siteUrl=site, feedpath=path).execute()
    return {"status": "submitted", "siteUrl": site, "feedpath": path}


@server.tool()
@require_google_service(SC, WRITE)
@handle_gsc_errors("delete_sitemap")
async def delete_sitemap(
    service: Resource,
    user_google_email: str,
    site_url: str,
    feedpath: str,
) -> Dict[str, Any]:
    """
    Delete (unsubmit) a sitemap from a Search Console property.

    Args:
        user_google_email: The user's Google email address. Required.
        site_url: The property, e.g. "https://example.com/" or "sc-domain:example.com".
        feedpath: The full URL of the sitemap to delete, e.g.
            "https://example.com/sitemap.xml".

    Returns:
        A confirmation dict; the API returns an empty body on success.
    """
    logger.info(f"[delete_sitemap] Invoked. Email: '{user_google_email}'")
    site = require_non_empty(site_url, "site_url")
    path = require_non_empty(feedpath, "feedpath")
    service.sitemaps().delete(siteUrl=site, feedpath=path).execute()
    return {"status": "deleted", "siteUrl": site, "feedpath": path}
