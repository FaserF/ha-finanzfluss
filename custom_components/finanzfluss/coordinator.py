"""DataUpdateCoordinator for Finanzfluss integration."""

import asyncio
from datetime import datetime, timedelta
import random

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import storage
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import CannotConnectError, FinanzflussAPI, InvalidAuthError
from .const import (
    CONF_FF_ACCESS_TOKEN,
    CONF_REFRESH_TOKEN,
    CONF_WAPI_ACCESS_TOKEN,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    LOGGER,
)


class FinanzflussDataUpdateCoordinator(DataUpdateCoordinator[dict]):
    """Class to manage fetching Finanzfluss data with anti-ban mechanisms."""

    def __init__(
        self, hass: HomeAssistant, api: FinanzflussAPI, entry: ConfigEntry
    ) -> None:
        """Initialize the coordinator."""
        self.api = api
        self.config_entry = entry
        self._backoff_until: datetime | None = None
        self._consecutive_failures: int = 0
        self._last_success: datetime | None = None

        # HA persistent storage for restart-resistance
        self.store = storage.Store(hass, 1, f"{DOMAIN}_coordinator_state")

        # Explicitly assign config_entry to the hass data update coordinator lookup table if available
        # to pass context verification checks
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )

    async def async_load_cache(self) -> None:
        """Load state cache from HA storage."""
        cache = await self.store.async_load()
        if cache:
            if "last_success" in cache:
                try:
                    self._last_success = dt_util.parse_datetime(cache["last_success"])
                except (ValueError, TypeError):
                    self._last_success = None

    async def _async_update_data(self) -> dict:
        """Fetch data from Finanzfluss API with jitter, locking, and backoff."""
        # 1. Backoff guard
        if self._backoff_until and dt_util.now() < self._backoff_until:
            LOGGER.debug(
                "Skipping update – backoff active until %s",
                self._backoff_until,
            )
            if self.data:
                return self.data
            raise UpdateFailed(f"Rate limited/Backing off until {self._backoff_until}")

        # 2. Restart resistance: Skip if last success was extremely recent
        if self._last_success is not None:
            time_since = dt_util.now() - self._last_success
            effective_interval = self.update_interval or timedelta(
                seconds=DEFAULT_SCAN_INTERVAL
            )
            # If we restarted and want to update, but did so within interval minus 1 minute
            if time_since < (effective_interval - timedelta(minutes=1)):
                LOGGER.debug(
                    "Skipping update: last success was %d seconds ago (recent)",
                    time_since.total_seconds(),
                )
                if self.data:
                    return self.data

        # 3. Domain-wide Lock to serialize concurrent requests (e.g. if multiple entries existed)
        domain_data = self.hass.data.setdefault(DOMAIN, {})
        fetch_lock: asyncio.Lock = domain_data.setdefault("fetch_lock", asyncio.Lock())

        async with fetch_lock:
            # 4. Jitter: sleep 5-30s if we have run successfully before to avoid concurrent spikes
            if self._last_success is not None:
                jitter = random.uniform(5.0, 30.0)
                LOGGER.debug("Waiting %.1f s jitter before API request", jitter)
                await asyncio.sleep(jitter)

            ff_token = self.config_entry.data.get(CONF_FF_ACCESS_TOKEN)
            wapi_token = self.config_entry.data.get(CONF_WAPI_ACCESS_TOKEN)
            refresh_token = self.config_entry.data.get(CONF_REFRESH_TOKEN)

            try:
                data = await self._fetch_all_data(ff_token, wapi_token)
                self._last_success = dt_util.now()
                self._consecutive_failures = 0
                self._backoff_until = None

                # Persist last success to HA storage
                await self.store.async_save(
                    {"last_success": self._last_success.isoformat()}
                )
                return data

            except InvalidAuthError:
                LOGGER.info("Tokens expired, attempting to refresh...")
                try:
                    auth_data = await self.api.refresh_tokens(refresh_token)

                    # Update config entry with new tokens
                    new_data = {**self.config_entry.data}
                    new_data[CONF_FF_ACCESS_TOKEN] = auth_data["ffAccessToken"]
                    new_data[CONF_WAPI_ACCESS_TOKEN] = auth_data["wapiAccessToken"]
                    new_data[CONF_REFRESH_TOKEN] = auth_data["refreshToken"]
                    self.hass.config_entries.async_update_entry(
                        self.config_entry, data=new_data
                    )

                    # Retry fetching with new tokens
                    data = await self._fetch_all_data(
                        auth_data["ffAccessToken"], auth_data["wapiAccessToken"]
                    )
                    self._last_success = dt_util.now()
                    self._consecutive_failures = 0
                    self._backoff_until = None
                    await self.store.async_save(
                        {"last_success": self._last_success.isoformat()}
                    )
                    return data

                except InvalidAuthError as refresh_err:
                    self._handle_failure(refresh_err)
                    raise ConfigEntryAuthFailed(
                        "Authentication expired, please reconfigure"
                    ) from refresh_err
                except CannotConnectError as conn_err:
                    self._handle_failure(conn_err)
                    raise UpdateFailed(
                        "Connection error during token refresh"
                    ) from conn_err
            except CannotConnectError as conn_err:
                self._handle_failure(conn_err)
                raise UpdateFailed("Connection error during data fetch") from conn_err
            except Exception as err:
                self._handle_failure(err)
                raise UpdateFailed(f"Unexpected error fetching data: {err}") from err

    def _handle_failure(self, err: Exception) -> None:
        """Handle consecutive failures and calculate backoff."""
        self._consecutive_failures += 1
        err_str = str(err).lower()

        # Exponential backoff on 403 / 429
        if "403" in err_str or "429" in err_str:
            backoff_hours = min(24, self._consecutive_failures * 2)
            self._backoff_until = dt_util.now() + timedelta(hours=backoff_hours)
            LOGGER.warning(
                "Rate limit/block detected. Backing off %d hours.", backoff_hours
            )
        else:
            backoff_minutes = min(240, self._consecutive_failures * 30)
            self._backoff_until = dt_util.now() + timedelta(minutes=backoff_minutes)
            LOGGER.warning(
                "Fetch failure #%d. Backing off %d minutes.",
                self._consecutive_failures,
                backoff_minutes,
            )

    async def _fetch_all_data(self, ff_token: str, wapi_token: str) -> dict:
        """Helper to fetch all data from API endpoints."""
        now = datetime.now()
        month_str = now.strftime("%Y-%m-01")
        start_date = (now - timedelta(days=365)).strftime("%Y-%m-%d")
        end_date = now.strftime("%Y-%m-%d")

        # Required
        accounts_data = await self.api.get_accounts(ff_token, wapi_token)
        budgets_data = await self.api.get_budgets(ff_token, month_str)

        # Optional — each wrapped in try/except, logs warning on failure
        inflation_data = None
        try:
            inflation_data = await self.api.get_inflation(
                ff_token, start_date, end_date
            )
        except Exception as err:
            LOGGER.warning("Could not fetch inflation data: %s", err)

        cashflow_data = None
        try:
            cashflow_data = await self.api.get_cashflow_summary(ff_token, month_str)
        except Exception as err:
            LOGGER.warning("Could not fetch cashflow data: %s", err)

        transactions_data = None
        try:
            transactions_data = await self.api.get_transactions(ff_token)
        except Exception as err:
            LOGGER.warning("Could not fetch transactions data: %s", err)

        investments_data = None
        try:
            investments_data = await self.api.get_investments(ff_token, wapi_token)
        except Exception as err:
            LOGGER.warning("Could not fetch investments data: %s", err)

        exemption_data = None
        try:
            exemption_data = await self.api.get_exemption_orders(ff_token)
        except Exception as err:
            LOGGER.warning("Could not fetch exemption orders data: %s", err)

        subscription_data = None
        try:
            subscription_data = await self.api.get_subscription(ff_token)
        except Exception as err:
            LOGGER.warning("Could not fetch subscription data: %s", err)

        categories_data = None
        try:
            categories_data = await self.api.get_categories(ff_token)
        except Exception as err:
            LOGGER.warning("Could not fetch categories data: %s", err)

        return {
            "accounts": accounts_data.get("accounts", []),
            "budgets": budgets_data,
            "inflation": inflation_data.get("rows", [])
            if isinstance(inflation_data, dict)
            else [],
            "cashflow": cashflow_data,
            "transactions": transactions_data,
            "investments": investments_data,
            "exemption_orders": exemption_data
            if isinstance(exemption_data, list)
            else [],
            "subscription": subscription_data,
            "categories": categories_data if isinstance(categories_data, list) else [],
        }
