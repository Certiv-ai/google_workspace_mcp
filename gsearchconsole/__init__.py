"""
Google Search Console (GSC) MCP Integration

This module provides MCP tools for reading Search Console performance data and managing
sitemaps via the Google Search Console API (searchconsole v1, which supersedes the legacy
webmasters v3 discovery and covers sites, sitemaps, searchAnalytics, and urlInspection).

Importing this package registers both the read and sitemap-write tools so a single
SERVICE_MODULES entry ("searchconsole" -> "gsearchconsole") loads the full tool set.
"""

from . import searchconsole_tools, sitemap_tools  # noqa: F401  (imported for registration)
