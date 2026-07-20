"""Tests for the Finanzfluss DataUpdateCoordinator."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.finanzfluss.api import (
    CannotConnectError,
    InvalidAuthError,
)
from custom_components.finanzfluss.coordinator import FinanzflussDataUpdateCoordinator

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_coordinator(
    hass, mock_config_entry, mock_api
) -> FinanzflussDataUpdateCoordinator:
    """Create a coordinator with mocked storage and a pre-configured config entry."""
    mock_config_entry.add_to_hass(hass)

    with patch("custom_components.finanzfluss.coordinator.storage.Store") as store_cls:
        store = AsyncMock()
        store.async_load.return_value = None
        store.async_save = AsyncMock()
        store_cls.return_value = store

        coordinator = FinanzflussDataUpdateCoordinator(
            hass, mock_api, mock_config_entry
        )
        coordinator.store = store
        return coordinator


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_all_data_success(
    hass, mock_config_entry, mock_api, sample_coordinator_data
):
    """Coordinator successfully fetches and returns all data keys."""
    coordinator = _make_coordinator(hass, mock_config_entry, mock_api)

    result = await coordinator._fetch_all_data("ff_token", "wapi_token")

    assert "accounts" in result
    assert "budgets" in result
    assert "inflation" in result
    assert "cashflow" in result
    assert "transactions" in result
    assert "investments" in result
    assert "exemption_orders" in result
    assert "subscription" in result
    assert "categories" in result

    # Verify accounts were flattened from the API response wrapper
    assert isinstance(result["accounts"], list)


@pytest.mark.asyncio
async def test_backoff_guard_returns_cached_data(hass, mock_config_entry, mock_api):
    """When backoff is active, skip API calls and return cached data."""
    coordinator = _make_coordinator(hass, mock_config_entry, mock_api)

    # Set backoff well into the future
    from homeassistant.util import dt as dt_util

    coordinator._backoff_until = dt_util.now() + timedelta(hours=2)
    coordinator.data = {"accounts": [{"id": 99}], "budgets": {}}

    result = await coordinator._async_update_data()

    # API should NOT have been called
    mock_api.get_accounts.assert_not_called()
    assert result["accounts"][0]["id"] == 99


@pytest.mark.asyncio
async def test_backoff_guard_raises_update_failed_when_no_cache(
    hass, mock_config_entry, mock_api
):
    """When backoff is active and no cached data, raise UpdateFailed."""
    coordinator = _make_coordinator(hass, mock_config_entry, mock_api)

    from homeassistant.util import dt as dt_util

    coordinator._backoff_until = dt_util.now() + timedelta(hours=2)
    coordinator.data = None  # no cached data

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


@pytest.mark.asyncio
async def test_token_refresh_on_auth_error(
    hass, mock_config_entry, mock_api, sample_coordinator_data
):
    """When _fetch_all_data raises InvalidAuthError, tokens are refreshed and data is returned."""
    coordinator = _make_coordinator(hass, mock_config_entry, mock_api)

    # First call raises auth error; second call (after refresh) succeeds
    call_count = 0

    async def fetch_side_effect(ff_token, wapi_token):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise InvalidAuthError("token expired")
        return sample_coordinator_data

    coordinator._fetch_all_data = fetch_side_effect  # type: ignore[method-assign]

    mock_api.refresh_tokens.return_value = {
        "ffAccessToken": "new_ff",
        "wapiAccessToken": "new_wapi",
        "refreshToken": "new_rt",
    }

    result = await coordinator._async_update_data()
    assert result is not None
    mock_api.refresh_tokens.assert_called_once()


@pytest.mark.asyncio
async def test_auth_failed_raises_config_entry_auth_failed(
    hass, mock_config_entry, mock_api
):
    """When both fetch and refresh fail, ConfigEntryAuthFailed is raised."""
    coordinator = _make_coordinator(hass, mock_config_entry, mock_api)

    async def always_fail(ff_token, wapi_token):
        raise InvalidAuthError("always fails")

    coordinator._fetch_all_data = always_fail  # type: ignore[method-assign]
    mock_api.refresh_tokens.side_effect = InvalidAuthError("refresh also fails")

    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator._async_update_data()


@pytest.mark.asyncio
async def test_optional_endpoints_graceful_on_failure(
    hass, mock_config_entry, mock_api
):
    """If optional endpoint like cashflow fails, coordinator returns data with cashflow=None."""
    mock_api.get_cashflow_summary.side_effect = Exception("endpoint unavailable")

    coordinator = _make_coordinator(hass, mock_config_entry, mock_api)

    result = await coordinator._fetch_all_data("ff_token", "wapi_token")

    assert result["cashflow"] is None
    # Required endpoints still present
    assert "accounts" in result
    assert "budgets" in result


@pytest.mark.asyncio
async def test_investments_graceful_on_failure(hass, mock_config_entry, mock_api):
    """If investments endpoint fails, investments key is None and no crash."""
    mock_api.get_investments.side_effect = Exception("depot unavailable")

    coordinator = _make_coordinator(hass, mock_config_entry, mock_api)
    result = await coordinator._fetch_all_data("ff_token", "wapi_token")

    assert result["investments"] is None


@pytest.mark.asyncio
async def test_consecutive_failure_increases_backoff(hass, mock_config_entry, mock_api):
    """_handle_failure sets backoff_until and increments consecutive_failures."""
    coordinator = _make_coordinator(hass, mock_config_entry, mock_api)

    coordinator._handle_failure(Exception("some error"))
    assert coordinator._consecutive_failures == 1
    assert coordinator._backoff_until is not None

    first_backoff = coordinator._backoff_until
    coordinator._handle_failure(Exception("another error"))
    assert coordinator._consecutive_failures == 2
    assert coordinator._backoff_until >= first_backoff


@pytest.mark.asyncio
async def test_rate_limit_triggers_long_backoff(hass, mock_config_entry, mock_api):
    """A 429 error triggers a longer (hours) backoff."""
    coordinator = _make_coordinator(hass, mock_config_entry, mock_api)

    coordinator._handle_failure(Exception("HTTP 429 Too Many Requests"))

    from homeassistant.util import dt as dt_util

    # backoff_until should be significantly into the future (at least 1 hour)
    assert coordinator._backoff_until > dt_util.now() + timedelta(minutes=30)


@pytest.mark.asyncio
async def test_connection_error_raises_update_failed(hass, mock_config_entry, mock_api):
    """CannotConnectError is wrapped in UpdateFailed."""
    coordinator = _make_coordinator(hass, mock_config_entry, mock_api)
    mock_api.get_accounts.side_effect = CannotConnectError("network error")

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()
