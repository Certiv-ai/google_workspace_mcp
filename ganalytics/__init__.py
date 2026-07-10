"""
Google Analytics 4 (GA4) MCP Integration

This module provides MCP tools for configuring and verifying GA4 tracking via the
Google Analytics Admin API (analyticsadmin) and the Data API (analyticsdata).

Importing this package registers both the Admin and Data API tools so a single
SERVICE_MODULES entry ("analytics" -> "ganalytics") loads the full tool set.
"""

from . import admin_tools, data_tools  # noqa: F401  (imported for tool registration)
