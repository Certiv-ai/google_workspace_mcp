"""
Scope-wiring and registration regression tests for the Alert Center tools.

These lock the auth contract so a future edit can't silently break it:
  - read tools must resolve to the logical Alert Center read scope, which the full
    apps.alerts scope covers via SCOPE_HIERARCHY (Google publishes no real
    apps.alerts.readonly scope, so consent must never request one);
  - the feedback-write tool must resolve to the full apps.alerts scope;
  - the service is registered in SERVICE_MODULES, the discovery config, and the tiers.
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from auth.scopes import (  # noqa: E402
    ALERT_CENTER_READONLY_SCOPE,
    ALERT_CENTER_SCOPE,
    SCOPE_HIERARCHY,
    TOOL_READONLY_SCOPES_MAP,
    TOOL_SCOPES_MAP,
    get_scopes_for_tools,
    has_required_scopes,
)
from auth.service_decorator import SCOPE_GROUPS, SERVICE_CONFIGS  # noqa: E402
from galertcenter import alert_tools, feedback_tools  # noqa: E402


def test_read_tools_use_read_scope_group():
    assert alert_tools.READ == "alertcenter_read"
    assert SCOPE_GROUPS["alertcenter_read"] == ALERT_CENTER_READONLY_SCOPE


def test_write_tool_uses_full_scope_group():
    assert feedback_tools.WRITE == "alertcenter"
    assert SCOPE_GROUPS["alertcenter"] == ALERT_CENTER_SCOPE


def test_full_scope_covers_read_scope():
    assert ALERT_CENTER_READONLY_SCOPE in SCOPE_HIERARCHY[ALERT_CENTER_SCOPE]
    # A token holding only the real apps.alerts scope satisfies the read tools.
    assert has_required_scopes([ALERT_CENTER_SCOPE], [ALERT_CENTER_READONLY_SCOPE])


def test_consent_never_requests_nonexistent_readonly_scope():
    # The apps.alerts.readonly scope is not published by Google; it must never be
    # requested at consent time, in either full or read-only mode.
    assert TOOL_SCOPES_MAP["alertcenter"] == [ALERT_CENTER_SCOPE]
    assert TOOL_READONLY_SCOPES_MAP["alertcenter"] == [ALERT_CENTER_SCOPE]
    assert ALERT_CENTER_READONLY_SCOPE not in get_scopes_for_tools(["alertcenter"])
    assert ALERT_CENTER_SCOPE in get_scopes_for_tools(["alertcenter"])


def test_service_discovery_config_is_v1beta1():
    assert SERVICE_CONFIGS["alertcenter"] == {
        "service": "alertcenter",
        "version": "v1beta1",
    }


def test_service_registered_in_service_modules():
    # Imported lazily so this test does not depend on main's import-time side effects.
    import main

    assert main.SERVICE_MODULES["alertcenter"] == "galertcenter"
    assert "alertcenter" in main.VALID_SERVICES
