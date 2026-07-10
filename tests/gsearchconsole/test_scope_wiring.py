"""
Scope-wiring regression tests for the Search Console tools.

These lock the auth contract so a future edit can't silently downgrade a write tool to a
read-only token (which would 403 at call time with a misleading property-ownership hint
instead of failing fast): read tools must resolve to webmasters.readonly and sitemap-write
tools must resolve to the full webmasters scope, which in turn must cover readonly.
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from auth.scopes import (  # noqa: E402
    SCOPE_HIERARCHY,
    SEARCH_CONSOLE_READONLY_SCOPE,
    SEARCH_CONSOLE_SCOPE,
    TOOL_READONLY_SCOPES_MAP,
    TOOL_SCOPES_MAP,
)
from auth.service_decorator import SCOPE_GROUPS  # noqa: E402
from gsearchconsole import searchconsole_tools, sitemap_tools  # noqa: E402


def test_read_tools_use_readonly_scope_group():
    assert searchconsole_tools.READ == "searchconsole_read"
    assert SCOPE_GROUPS["searchconsole_read"] == SEARCH_CONSOLE_READONLY_SCOPE


def test_write_tools_use_full_scope_group():
    assert sitemap_tools.WRITE == "searchconsole"
    assert SCOPE_GROUPS["searchconsole"] == SEARCH_CONSOLE_SCOPE


def test_write_scope_covers_readonly():
    assert SEARCH_CONSOLE_READONLY_SCOPE in SCOPE_HIERARCHY[SEARCH_CONSOLE_SCOPE]


def test_tool_scope_maps_registered():
    assert SEARCH_CONSOLE_SCOPE in TOOL_SCOPES_MAP["searchconsole"]
    assert TOOL_READONLY_SCOPES_MAP["searchconsole"] == [SEARCH_CONSOLE_READONLY_SCOPE]
