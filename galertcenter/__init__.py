"""
Google Workspace Alert Center MCP Integration

This module provides MCP tools for reading and triaging Google Workspace admin security
alerts via the Alert Center API (alertcenter v1beta1, discovery service name
"alertcenter"). It exposes read tools (list/get alerts, get alert metadata, list feedback)
and one non-destructive feedback-write tool; it intentionally does NOT wrap the
destructive delete/undelete/batch endpoints.

Importing this package registers both the read and feedback tools so a single
SERVICE_MODULES entry ("alertcenter" -> "galertcenter") loads the full tool set.
"""

from . import alert_tools, feedback_tools  # noqa: F401  (imported for registration)
