"""Diagnostics support for Finanzfluss."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN

TO_REDACT = {
    "password",
    "ff_access_token",
    "wapi_access_token",
    "refresh_token",
    "user_uuid",
    "uuid",
    "iban",
    "id",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    diagnostics_data = {
        "entry": {
            "entry_id": entry.entry_id,
            "version": entry.version,
            "domain": entry.domain,
            "title": entry.title,
            "data": async_redact_data(entry.data, TO_REDACT),
            "options": async_redact_data(entry.options, TO_REDACT),
        },
        "coordinator": {
            "consecutive_failures": coordinator._consecutive_failures,
            "last_success": coordinator._last_success.isoformat()
            if coordinator._last_success
            else None,
            "backoff_until": coordinator._backoff_until.isoformat()
            if coordinator._backoff_until
            else None,
            "has_data": coordinator.data is not None,
            "accounts_count": len(coordinator.data.get("accounts", []))
            if coordinator.data
            else 0,
            "buckets_count": len(coordinator.data.get("budgets", {}).get("buckets", []))
            if coordinator.data and isinstance(coordinator.data.get("budgets"), dict)
            else 0,
        },
    }

    return diagnostics_data
