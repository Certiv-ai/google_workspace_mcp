"""
Google Analytics 4 Admin API MCP Tools

Configuration / write side of GA4 tracking, backed by the Analytics Admin API
(analyticsadmin v1beta, with v1alpha for event-create and event-edit rules).

Read tools require the analytics.readonly scope; write tools require analytics.edit.
Every call 403s until paul@certiv.ai is granted a role on the target GA4 property in
GA Admin and the GA scopes are consented via bootstrap_auth.py; see summarize_ga_error.
"""

import logging
from typing import Any, Dict, List, Optional

from mcp import Resource

from auth.service_decorator import require_google_service
from core.server import server
from ganalytics.analytics_helpers import (
    handle_ga_errors,
    normalize_account_id,
    normalize_data_stream_name,
    normalize_property_id,
    require_fields,
)

logger = logging.getLogger(__name__)

ADMIN = "analyticsadmin"
READ = "analytics_read"
EDIT = "analytics_edit"


@server.tool()
@require_google_service(ADMIN, READ)
@handle_ga_errors("list_account_summaries", ADMIN)
async def list_account_summaries(
    service: Resource,
    user_google_email: str,
    page_size: int = 200,
    page_token: Optional[str] = None,
) -> Dict[str, Any]:
    """
    List GA4 account summaries visible to the authenticated user.

    Each summary carries the account resource name plus its child property summaries
    (property resource name + display name), so this is the fastest way to discover the
    property ids the other tools need.

    Args:
        user_google_email: The user's Google email address. Required.
        page_size: Max account summaries to return (default 200).
        page_token: Page token from a previous response for pagination.

    Returns:
        The accountSummaries.list response (accountSummaries + nextPageToken).
    """
    logger.info(f"[list_account_summaries] Invoked. Email: '{user_google_email}'")
    return (
        service.accountSummaries()
        .list(pageSize=page_size, pageToken=page_token)
        .execute()
    )


@server.tool()
@require_google_service(ADMIN, READ)
@handle_ga_errors("list_properties", ADMIN)
async def list_properties(
    service: Resource,
    user_google_email: str,
    account_id: str,
    page_size: int = 200,
    page_token: Optional[str] = None,
    show_deleted: bool = False,
) -> Dict[str, Any]:
    """
    List GA4 properties under a given account.

    Args:
        user_google_email: The user's Google email address. Required.
        account_id: GA4 account id ("123456") or resource name ("accounts/123456").
        page_size: Max properties to return (default 200).
        page_token: Page token from a previous response for pagination.
        show_deleted: Include soft-deleted properties still in the trash.

    Returns:
        The properties.list response (properties + nextPageToken).
    """
    logger.info(f"[list_properties] Invoked. Email: '{user_google_email}'")
    account = normalize_account_id(account_id)
    return (
        service.properties()
        .list(
            filter=f"parent:{account}",
            pageSize=page_size,
            pageToken=page_token,
            showDeleted=show_deleted,
        )
        .execute()
    )


@server.tool()
@require_google_service(ADMIN, READ)
@handle_ga_errors("get_property", ADMIN)
async def get_property(
    service: Resource,
    user_google_email: str,
    property_id: str,
) -> Dict[str, Any]:
    """
    Get a single GA4 property's configuration.

    Args:
        user_google_email: The user's Google email address. Required.
        property_id: GA4 property id ("123456789") or resource name.

    Returns:
        The property resource (displayName, timeZone, currencyCode, industryCategory, etc.).
    """
    logger.info(f"[get_property] Invoked. Email: '{user_google_email}'")
    return service.properties().get(name=normalize_property_id(property_id)).execute()


# --------------------------------------------------------------------------- #
# Custom dimensions
# --------------------------------------------------------------------------- #


@server.tool()
@require_google_service(ADMIN, READ)
@handle_ga_errors("list_custom_dimensions", ADMIN)
async def list_custom_dimensions(
    service: Resource,
    user_google_email: str,
    property_id: str,
    page_size: int = 200,
    page_token: Optional[str] = None,
) -> Dict[str, Any]:
    """
    List custom dimensions defined on a GA4 property.

    Args:
        user_google_email: The user's Google email address. Required.
        property_id: GA4 property id or resource name.
        page_size: Max custom dimensions to return (default 200).
        page_token: Page token for pagination.

    Returns:
        The customDimensions.list response.
    """
    logger.info(f"[list_custom_dimensions] Invoked. Email: '{user_google_email}'")
    return (
        service.properties()
        .customDimensions()
        .list(
            parent=normalize_property_id(property_id),
            pageSize=page_size,
            pageToken=page_token,
        )
        .execute()
    )


@server.tool()
@require_google_service(ADMIN, EDIT)
@handle_ga_errors("create_custom_dimension", ADMIN)
async def create_custom_dimension(
    service: Resource,
    user_google_email: str,
    property_id: str,
    parameter_name: str,
    display_name: str,
    scope: str = "EVENT",
    description: Optional[str] = None,
    disallow_ads_personalization: bool = False,
) -> Dict[str, Any]:
    """
    Create a custom dimension on a GA4 property.

    Args:
        user_google_email: The user's Google email address. Required.
        property_id: GA4 property id or resource name.
        parameter_name: Event/user parameter name to register (the tagging key).
        display_name: Human-readable name shown in the GA UI.
        scope: Dimension scope: "EVENT", "USER", or "ITEM" (default "EVENT").
        description: Optional description.
        disallow_ads_personalization: If True, mark as NPA (user-scoped only).

    Returns:
        The created customDimension resource.
    """
    logger.info(f"[create_custom_dimension] Invoked. Email: '{user_google_email}'")
    body: Dict[str, Any] = {
        "parameterName": parameter_name,
        "displayName": display_name,
        "scope": scope,
    }
    if description:
        body["description"] = description
    if disallow_ads_personalization:
        body["disallowAdsPersonalization"] = True
    require_fields(body, ["parameterName", "displayName", "scope"], "custom dimension")
    return (
        service.properties()
        .customDimensions()
        .create(parent=normalize_property_id(property_id), body=body)
        .execute()
    )


@server.tool()
@require_google_service(ADMIN, EDIT)
@handle_ga_errors("update_custom_dimension", ADMIN)
async def update_custom_dimension(
    service: Resource,
    user_google_email: str,
    custom_dimension_name: str,
    display_name: Optional[str] = None,
    description: Optional[str] = None,
    disallow_ads_personalization: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    Update mutable fields of a custom dimension (displayName, description, NPA flag).

    parameterName and scope are immutable in GA4 and cannot be changed here.

    Args:
        user_google_email: The user's Google email address. Required.
        custom_dimension_name: Full resource name
            ("properties/123/customDimensions/456").
        display_name: New display name, if changing.
        description: New description, if changing.
        disallow_ads_personalization: New NPA flag, if changing.

    Returns:
        The updated customDimension resource.
    """
    logger.info(f"[update_custom_dimension] Invoked. Email: '{user_google_email}'")
    body: Dict[str, Any] = {}
    update_mask: List[str] = []
    if display_name is not None:
        body["displayName"] = display_name
        update_mask.append("displayName")
    if description is not None:
        body["description"] = description
        update_mask.append("description")
    if disallow_ads_personalization is not None:
        body["disallowAdsPersonalization"] = disallow_ads_personalization
        update_mask.append("disallowAdsPersonalization")
    if not update_mask:
        require_fields({}, ["display_name|description|disallow_ads_personalization"],
                       "update_custom_dimension")
    return (
        service.properties()
        .customDimensions()
        .patch(
            name=custom_dimension_name,
            updateMask=",".join(update_mask),
            body=body,
        )
        .execute()
    )


@server.tool()
@require_google_service(ADMIN, EDIT)
@handle_ga_errors("archive_custom_dimension", ADMIN)
async def archive_custom_dimension(
    service: Resource,
    user_google_email: str,
    custom_dimension_name: str,
) -> Dict[str, Any]:
    """
    Archive (soft-delete) a custom dimension. GA4 has no hard delete for these.

    Args:
        user_google_email: The user's Google email address. Required.
        custom_dimension_name: Full resource name
            ("properties/123/customDimensions/456").

    Returns:
        An empty object on success.
    """
    logger.info(f"[archive_custom_dimension] Invoked. Email: '{user_google_email}'")
    return (
        service.properties()
        .customDimensions()
        .archive(name=custom_dimension_name, body={})
        .execute()
    )


# --------------------------------------------------------------------------- #
# Custom metrics
# --------------------------------------------------------------------------- #


@server.tool()
@require_google_service(ADMIN, READ)
@handle_ga_errors("list_custom_metrics", ADMIN)
async def list_custom_metrics(
    service: Resource,
    user_google_email: str,
    property_id: str,
    page_size: int = 200,
    page_token: Optional[str] = None,
) -> Dict[str, Any]:
    """
    List custom metrics defined on a GA4 property.

    Args:
        user_google_email: The user's Google email address. Required.
        property_id: GA4 property id or resource name.
        page_size: Max custom metrics to return (default 200).
        page_token: Page token for pagination.

    Returns:
        The customMetrics.list response.
    """
    logger.info(f"[list_custom_metrics] Invoked. Email: '{user_google_email}'")
    return (
        service.properties()
        .customMetrics()
        .list(
            parent=normalize_property_id(property_id),
            pageSize=page_size,
            pageToken=page_token,
        )
        .execute()
    )


@server.tool()
@require_google_service(ADMIN, EDIT)
@handle_ga_errors("create_custom_metric", ADMIN)
async def create_custom_metric(
    service: Resource,
    user_google_email: str,
    property_id: str,
    parameter_name: str,
    display_name: str,
    measurement_unit: str,
    scope: str = "EVENT",
    description: Optional[str] = None,
    restricted_metric_types: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Create a custom metric on a GA4 property.

    Args:
        user_google_email: The user's Google email address. Required.
        property_id: GA4 property id or resource name.
        parameter_name: Event parameter name to register as a metric.
        display_name: Human-readable name shown in the GA UI.
        measurement_unit: One of STANDARD, CURRENCY, FEET, MILES, METERS, KILOMETERS,
            MILLISECONDS, SECONDS, MINUTES, HOURS.
        scope: Metric scope, currently only "EVENT" (default "EVENT").
        description: Optional description.
        restricted_metric_types: Optional list, e.g. ["COST_DATA"] or ["REVENUE_DATA"].

    Returns:
        The created customMetric resource.
    """
    logger.info(f"[create_custom_metric] Invoked. Email: '{user_google_email}'")
    body: Dict[str, Any] = {
        "parameterName": parameter_name,
        "displayName": display_name,
        "measurementUnit": measurement_unit,
        "scope": scope,
    }
    if description:
        body["description"] = description
    if restricted_metric_types:
        body["restrictedMetricType"] = restricted_metric_types
    require_fields(
        body,
        ["parameterName", "displayName", "measurementUnit", "scope"],
        "custom metric",
    )
    return (
        service.properties()
        .customMetrics()
        .create(parent=normalize_property_id(property_id), body=body)
        .execute()
    )


@server.tool()
@require_google_service(ADMIN, EDIT)
@handle_ga_errors("update_custom_metric", ADMIN)
async def update_custom_metric(
    service: Resource,
    user_google_email: str,
    custom_metric_name: str,
    display_name: Optional[str] = None,
    description: Optional[str] = None,
    measurement_unit: Optional[str] = None,
    restricted_metric_types: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Update mutable fields of a custom metric.

    parameterName and scope are immutable in GA4 and cannot be changed here.

    Args:
        user_google_email: The user's Google email address. Required.
        custom_metric_name: Full resource name ("properties/123/customMetrics/456").
        display_name: New display name, if changing.
        description: New description, if changing.
        measurement_unit: New measurement unit, if changing.
        restricted_metric_types: New restricted metric types, if changing.

    Returns:
        The updated customMetric resource.
    """
    logger.info(f"[update_custom_metric] Invoked. Email: '{user_google_email}'")
    body: Dict[str, Any] = {}
    update_mask: List[str] = []
    if display_name is not None:
        body["displayName"] = display_name
        update_mask.append("displayName")
    if description is not None:
        body["description"] = description
        update_mask.append("description")
    if measurement_unit is not None:
        body["measurementUnit"] = measurement_unit
        update_mask.append("measurementUnit")
    if restricted_metric_types is not None:
        body["restrictedMetricType"] = restricted_metric_types
        update_mask.append("restrictedMetricType")
    if not update_mask:
        require_fields({}, ["display_name|description|measurement_unit|"
                            "restricted_metric_types"], "update_custom_metric")
    return (
        service.properties()
        .customMetrics()
        .patch(name=custom_metric_name, updateMask=",".join(update_mask), body=body)
        .execute()
    )


@server.tool()
@require_google_service(ADMIN, EDIT)
@handle_ga_errors("archive_custom_metric", ADMIN)
async def archive_custom_metric(
    service: Resource,
    user_google_email: str,
    custom_metric_name: str,
) -> Dict[str, Any]:
    """
    Archive (soft-delete) a custom metric. GA4 has no hard delete for these.

    Args:
        user_google_email: The user's Google email address. Required.
        custom_metric_name: Full resource name ("properties/123/customMetrics/456").

    Returns:
        An empty object on success.
    """
    logger.info(f"[archive_custom_metric] Invoked. Email: '{user_google_email}'")
    return (
        service.properties()
        .customMetrics()
        .archive(name=custom_metric_name, body={})
        .execute()
    )


# --------------------------------------------------------------------------- #
# Key events (conversions)
# --------------------------------------------------------------------------- #


@server.tool()
@require_google_service(ADMIN, READ)
@handle_ga_errors("list_key_events", ADMIN)
async def list_key_events(
    service: Resource,
    user_google_email: str,
    property_id: str,
    page_size: int = 200,
    page_token: Optional[str] = None,
) -> Dict[str, Any]:
    """
    List key events (the GA4 replacement for conversions) on a property.

    Args:
        user_google_email: The user's Google email address. Required.
        property_id: GA4 property id or resource name.
        page_size: Max key events to return (default 200).
        page_token: Page token for pagination.

    Returns:
        The keyEvents.list response.
    """
    logger.info(f"[list_key_events] Invoked. Email: '{user_google_email}'")
    return (
        service.properties()
        .keyEvents()
        .list(
            parent=normalize_property_id(property_id),
            pageSize=page_size,
            pageToken=page_token,
        )
        .execute()
    )


@server.tool()
@require_google_service(ADMIN, EDIT)
@handle_ga_errors("create_key_event", ADMIN)
async def create_key_event(
    service: Resource,
    user_google_email: str,
    property_id: str,
    event_name: str,
    counting_method: str = "ONCE_PER_EVENT",
    default_currency_code: Optional[str] = None,
    default_value: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Mark an event as a key event (conversion) on a GA4 property.

    Args:
        user_google_email: The user's Google email address. Required.
        property_id: GA4 property id or resource name.
        event_name: The event name to mark as a key event (e.g. "purchase").
        counting_method: "ONCE_PER_EVENT" or "ONCE_PER_SESSION" (default ONCE_PER_EVENT).
        default_currency_code: Optional ISO 4217 currency for the default value.
        default_value: Optional default numeric value; requires default_currency_code.

    Returns:
        The created keyEvent resource.
    """
    logger.info(f"[create_key_event] Invoked. Email: '{user_google_email}'")
    body: Dict[str, Any] = {
        "eventName": event_name,
        "countingMethod": counting_method,
    }
    if default_value is not None or default_currency_code:
        require_fields(
            {"default_value": default_value, "default_currency_code": default_currency_code},
            ["default_value", "default_currency_code"],
            "key event default value",
        )
        body["defaultValue"] = {
            "numericValue": default_value,
            "currencyCode": default_currency_code,
        }
    return (
        service.properties()
        .keyEvents()
        .create(parent=normalize_property_id(property_id), body=body)
        .execute()
    )


@server.tool()
@require_google_service(ADMIN, EDIT)
@handle_ga_errors("delete_key_event", ADMIN)
async def delete_key_event(
    service: Resource,
    user_google_email: str,
    key_event_name: str,
) -> Dict[str, Any]:
    """
    Delete a key event (stop treating an event as a conversion).

    Args:
        user_google_email: The user's Google email address. Required.
        key_event_name: Full resource name ("properties/123/keyEvents/456").

    Returns:
        An empty object on success.
    """
    logger.info(f"[delete_key_event] Invoked. Email: '{user_google_email}'")
    service.properties().keyEvents().delete(name=key_event_name).execute()
    return {"deleted": key_event_name}


# --------------------------------------------------------------------------- #
# Data streams
# --------------------------------------------------------------------------- #


@server.tool()
@require_google_service(ADMIN, READ)
@handle_ga_errors("list_data_streams", ADMIN)
async def list_data_streams(
    service: Resource,
    user_google_email: str,
    property_id: str,
    page_size: int = 200,
    page_token: Optional[str] = None,
) -> Dict[str, Any]:
    """
    List data streams (web / iOS / Android) on a GA4 property.

    Args:
        user_google_email: The user's Google email address. Required.
        property_id: GA4 property id or resource name.
        page_size: Max data streams to return (default 200).
        page_token: Page token for pagination.

    Returns:
        The dataStreams.list response, including each stream's measurement id.
    """
    logger.info(f"[list_data_streams] Invoked. Email: '{user_google_email}'")
    return (
        service.properties()
        .dataStreams()
        .list(
            parent=normalize_property_id(property_id),
            pageSize=page_size,
            pageToken=page_token,
        )
        .execute()
    )


@server.tool()
@require_google_service(ADMIN, READ)
@handle_ga_errors("get_data_stream", ADMIN)
async def get_data_stream(
    service: Resource,
    user_google_email: str,
    property_id: str,
    data_stream_id: str,
) -> Dict[str, Any]:
    """
    Get a single data stream's configuration (including the web measurement id).

    Args:
        user_google_email: The user's Google email address. Required.
        property_id: GA4 property id or resource name (used only if data_stream_id is bare).
        data_stream_id: Stream id or full "properties/123/dataStreams/456" resource name.

    Returns:
        The dataStream resource.
    """
    logger.info(f"[get_data_stream] Invoked. Email: '{user_google_email}'")
    name = normalize_data_stream_name(property_id, data_stream_id)
    return service.properties().dataStreams().get(name=name).execute()


# --------------------------------------------------------------------------- #
# Measurement Protocol secrets (server-side event sends)
# --------------------------------------------------------------------------- #


@server.tool()
@require_google_service(ADMIN, READ)
@handle_ga_errors("list_measurement_protocol_secrets", ADMIN)
async def list_measurement_protocol_secrets(
    service: Resource,
    user_google_email: str,
    property_id: str,
    data_stream_id: str,
    page_size: int = 200,
    page_token: Optional[str] = None,
) -> Dict[str, Any]:
    """
    List Measurement Protocol secrets for a data stream.

    Args:
        user_google_email: The user's Google email address. Required.
        property_id: GA4 property id or resource name (used only if data_stream_id is bare).
        data_stream_id: Stream id or full data stream resource name.
        page_size: Max secrets to return (default 200).
        page_token: Page token for pagination.

    Returns:
        The measurementProtocolSecrets.list response.
    """
    logger.info(
        f"[list_measurement_protocol_secrets] Invoked. Email: '{user_google_email}'"
    )
    parent = normalize_data_stream_name(property_id, data_stream_id)
    return (
        service.properties()
        .dataStreams()
        .measurementProtocolSecrets()
        .list(parent=parent, pageSize=page_size, pageToken=page_token)
        .execute()
    )


@server.tool()
@require_google_service(ADMIN, EDIT)
@handle_ga_errors("create_measurement_protocol_secret", ADMIN)
async def create_measurement_protocol_secret(
    service: Resource,
    user_google_email: str,
    property_id: str,
    data_stream_id: str,
    display_name: str,
) -> Dict[str, Any]:
    """
    Create a Measurement Protocol secret, enabling server-side event sends for a stream.

    The returned resource includes secretValue; treat it as a credential.

    Args:
        user_google_email: The user's Google email address. Required.
        property_id: GA4 property id or resource name (used only if data_stream_id is bare).
        data_stream_id: Stream id or full data stream resource name.
        display_name: Human-readable name for the secret.

    Returns:
        The created measurementProtocolSecret resource (contains secretValue).
    """
    logger.info(
        f"[create_measurement_protocol_secret] Invoked. Email: '{user_google_email}'"
    )
    parent = normalize_data_stream_name(property_id, data_stream_id)
    return (
        service.properties()
        .dataStreams()
        .measurementProtocolSecrets()
        .create(parent=parent, body={"displayName": display_name})
        .execute()
    )


# --------------------------------------------------------------------------- #
# Event-create rules (v1alpha; nested under a data stream)
# --------------------------------------------------------------------------- #

ALPHA = "v1alpha"


@server.tool()
@require_google_service(ADMIN, READ, version=ALPHA)
@handle_ga_errors("list_event_create_rules", ADMIN)
async def list_event_create_rules(
    service: Resource,
    user_google_email: str,
    property_id: str,
    data_stream_id: str,
    page_size: int = 200,
    page_token: Optional[str] = None,
) -> Dict[str, Any]:
    """
    List event-create rules on a data stream (v1alpha).

    Event-create rules synthesize a new event when an existing event matches conditions.

    Args:
        user_google_email: The user's Google email address. Required.
        property_id: GA4 property id or resource name (used only if data_stream_id is bare).
        data_stream_id: Stream id or full data stream resource name.
        page_size: Max rules to return (default 200).
        page_token: Page token for pagination.

    Returns:
        The eventCreateRules.list response.
    """
    logger.info(f"[list_event_create_rules] Invoked. Email: '{user_google_email}'")
    parent = normalize_data_stream_name(property_id, data_stream_id)
    return (
        service.properties()
        .dataStreams()
        .eventCreateRules()
        .list(parent=parent, pageSize=page_size, pageToken=page_token)
        .execute()
    )


@server.tool()
@require_google_service(ADMIN, EDIT, version=ALPHA)
@handle_ga_errors("create_event_create_rule", ADMIN)
async def create_event_create_rule(
    service: Resource,
    user_google_email: str,
    property_id: str,
    data_stream_id: str,
    rule: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Create an event-create rule on a data stream (v1alpha).

    Args:
        user_google_email: The user's Google email address. Required.
        property_id: GA4 property id or resource name (used only if data_stream_id is bare).
        data_stream_id: Stream id or full data stream resource name.
        rule: The EventCreateRule body, e.g.
            {"destinationEvent": "generate_lead",
             "eventConditions": [{"field": "event_name", "comparisonType": "EQUALS",
                                  "value": "form_submit"}],
             "sourceCopyParameters": true,
             "parameterMutations": [{"parameter": "value", "parameterValue": "10"}]}.

    Returns:
        The created eventCreateRule resource.
    """
    logger.info(f"[create_event_create_rule] Invoked. Email: '{user_google_email}'")
    require_fields(rule, ["destinationEvent", "eventConditions"], "event-create rule")
    parent = normalize_data_stream_name(property_id, data_stream_id)
    return (
        service.properties()
        .dataStreams()
        .eventCreateRules()
        .create(parent=parent, body=rule)
        .execute()
    )


@server.tool()
@require_google_service(ADMIN, EDIT, version=ALPHA)
@handle_ga_errors("update_event_create_rule", ADMIN)
async def update_event_create_rule(
    service: Resource,
    user_google_email: str,
    event_create_rule_name: str,
    rule: Dict[str, Any],
    update_mask: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Update an event-create rule (v1alpha).

    Args:
        user_google_email: The user's Google email address. Required.
        event_create_rule_name: Full resource name
            ("properties/123/dataStreams/456/eventCreateRules/789").
        rule: Partial EventCreateRule body with the fields to change.
        update_mask: Field paths to update; defaults to the keys present in rule.

    Returns:
        The updated eventCreateRule resource.
    """
    logger.info(f"[update_event_create_rule] Invoked. Email: '{user_google_email}'")
    mask = update_mask if update_mask else list(rule.keys())
    require_fields({"rule": rule}, ["rule"], "update_event_create_rule")
    return (
        service.properties()
        .dataStreams()
        .eventCreateRules()
        .patch(
            name=event_create_rule_name,
            updateMask=",".join(mask),
            body=rule,
        )
        .execute()
    )


@server.tool()
@require_google_service(ADMIN, EDIT, version=ALPHA)
@handle_ga_errors("delete_event_create_rule", ADMIN)
async def delete_event_create_rule(
    service: Resource,
    user_google_email: str,
    event_create_rule_name: str,
) -> Dict[str, Any]:
    """
    Delete an event-create rule (v1alpha).

    Args:
        user_google_email: The user's Google email address. Required.
        event_create_rule_name: Full resource name
            ("properties/123/dataStreams/456/eventCreateRules/789").

    Returns:
        An empty object on success.
    """
    logger.info(f"[delete_event_create_rule] Invoked. Email: '{user_google_email}'")
    service.properties().dataStreams().eventCreateRules().delete(
        name=event_create_rule_name
    ).execute()
    return {"deleted": event_create_rule_name}


# --------------------------------------------------------------------------- #
# Event-edit rules (v1alpha; nested under a data stream)
# --------------------------------------------------------------------------- #


@server.tool()
@require_google_service(ADMIN, READ, version=ALPHA)
@handle_ga_errors("list_event_edit_rules", ADMIN)
async def list_event_edit_rules(
    service: Resource,
    user_google_email: str,
    property_id: str,
    data_stream_id: str,
    page_size: int = 200,
    page_token: Optional[str] = None,
) -> Dict[str, Any]:
    """
    List event-edit rules on a data stream (v1alpha).

    Event-edit rules rewrite parameters of an existing event before processing.

    Args:
        user_google_email: The user's Google email address. Required.
        property_id: GA4 property id or resource name (used only if data_stream_id is bare).
        data_stream_id: Stream id or full data stream resource name.
        page_size: Max rules to return (default 200).
        page_token: Page token for pagination.

    Returns:
        The eventEditRules.list response.
    """
    logger.info(f"[list_event_edit_rules] Invoked. Email: '{user_google_email}'")
    parent = normalize_data_stream_name(property_id, data_stream_id)
    return (
        service.properties()
        .dataStreams()
        .eventEditRules()
        .list(parent=parent, pageSize=page_size, pageToken=page_token)
        .execute()
    )


@server.tool()
@require_google_service(ADMIN, EDIT, version=ALPHA)
@handle_ga_errors("create_event_edit_rule", ADMIN)
async def create_event_edit_rule(
    service: Resource,
    user_google_email: str,
    property_id: str,
    data_stream_id: str,
    rule: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Create an event-edit rule on a data stream (v1alpha).

    Args:
        user_google_email: The user's Google email address. Required.
        property_id: GA4 property id or resource name (used only if data_stream_id is bare).
        data_stream_id: Stream id or full data stream resource name.
        rule: The EventEditRule body, e.g.
            {"displayName": "Fix currency",
             "eventConditions": [{"field": "event_name", "comparisonType": "EQUALS",
                                  "value": "purchase"}],
             "parameterMutations": [{"parameter": "currency", "parameterValue": "USD"}]}.

    Returns:
        The created eventEditRule resource.
    """
    logger.info(f"[create_event_edit_rule] Invoked. Email: '{user_google_email}'")
    require_fields(
        rule,
        ["displayName", "eventConditions", "parameterMutations"],
        "event-edit rule",
    )
    parent = normalize_data_stream_name(property_id, data_stream_id)
    return (
        service.properties()
        .dataStreams()
        .eventEditRules()
        .create(parent=parent, body=rule)
        .execute()
    )


@server.tool()
@require_google_service(ADMIN, EDIT, version=ALPHA)
@handle_ga_errors("update_event_edit_rule", ADMIN)
async def update_event_edit_rule(
    service: Resource,
    user_google_email: str,
    event_edit_rule_name: str,
    rule: Dict[str, Any],
    update_mask: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Update an event-edit rule (v1alpha).

    Args:
        user_google_email: The user's Google email address. Required.
        event_edit_rule_name: Full resource name
            ("properties/123/dataStreams/456/eventEditRules/789").
        rule: Partial EventEditRule body with the fields to change.
        update_mask: Field paths to update; defaults to the keys present in rule.

    Returns:
        The updated eventEditRule resource.
    """
    logger.info(f"[update_event_edit_rule] Invoked. Email: '{user_google_email}'")
    mask = update_mask if update_mask else list(rule.keys())
    require_fields({"rule": rule}, ["rule"], "update_event_edit_rule")
    return (
        service.properties()
        .dataStreams()
        .eventEditRules()
        .patch(name=event_edit_rule_name, updateMask=",".join(mask), body=rule)
        .execute()
    )


@server.tool()
@require_google_service(ADMIN, EDIT, version=ALPHA)
@handle_ga_errors("delete_event_edit_rule", ADMIN)
async def delete_event_edit_rule(
    service: Resource,
    user_google_email: str,
    event_edit_rule_name: str,
) -> Dict[str, Any]:
    """
    Delete an event-edit rule (v1alpha).

    Args:
        user_google_email: The user's Google email address. Required.
        event_edit_rule_name: Full resource name
            ("properties/123/dataStreams/456/eventEditRules/789").

    Returns:
        An empty object on success.
    """
    logger.info(f"[delete_event_edit_rule] Invoked. Email: '{user_google_email}'")
    service.properties().dataStreams().eventEditRules().delete(
        name=event_edit_rule_name
    ).execute()
    return {"deleted": event_edit_rule_name}
