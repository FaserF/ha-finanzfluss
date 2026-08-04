"""DataUpdateCoordinator for Finanzfluss integration."""

import asyncio
from datetime import datetime, timedelta
import random
from typing import Any

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
    CONF_SCAN_INTERVAL,
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
        self.store: storage.Store = storage.Store(
            hass, 1, f"{DOMAIN}_coordinator_state"
        )

        # Explicitly assign config_entry to the hass data update coordinator lookup table if available
        # to pass context verification checks
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(
                seconds=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            ),
        )

    async def async_load_cache(self) -> None:
        """Load state cache from HA storage."""
        cache = await self.store.async_load()
        if cache:
            if "last_success" in cache:
                try:
                    self._last_success = dt_util.parse_datetime(cache["last_success"])
                except Exception:  # noqa: BLE001
                    LOGGER.warning("Could not parse cached last_success date")

    async def _async_update_data(self) -> dict:
        """Fetch data from Finanzfluss API."""
        now = dt_util.now()

        # 1. Backoff Guard
        if self._backoff_until and now < self._backoff_until:
            LOGGER.warning(
                "In backoff period until %s due to API rate limiting / failures.",
                self._backoff_until,
            )
            if self.data:
                LOGGER.info("Returning cached coordinator data during backoff.")
                return self.data
            raise UpdateFailed(
                f"Rate limited. Waiting until {self._backoff_until.isoformat()} before retrying."
            )

        # 2. Check config entry
        entry = self.config_entry
        if not entry:
            raise UpdateFailed("Config entry is missing")

        # 3. Domain-wide Lock to serialize concurrent requests (e.g. if multiple entries existed)
        domain_data = self.hass.data.setdefault(DOMAIN, {})
        fetch_lock: asyncio.Lock = domain_data.setdefault("fetch_lock", asyncio.Lock())

        async with fetch_lock:
            # 4. Jitter: sleep 5-30s if we have run successfully before to avoid concurrent spikes
            if self._last_success is not None:
                jitter = random.uniform(5.0, 30.0)
                LOGGER.debug("Waiting %.1f s jitter before API request", jitter)
                await asyncio.sleep(jitter)

            ff_token: str = entry.data.get(CONF_FF_ACCESS_TOKEN, "")
            wapi_token: str = entry.data.get(CONF_WAPI_ACCESS_TOKEN, "")
            refresh_token: str = entry.data.get(CONF_REFRESH_TOKEN, "")

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
                    new_data = {**entry.data}
                    new_data[CONF_FF_ACCESS_TOKEN] = auth_data["ffAccessToken"]
                    new_data[CONF_WAPI_ACCESS_TOKEN] = auth_data["wapiAccessToken"]
                    new_data[CONF_REFRESH_TOKEN] = auth_data["refreshToken"]
                    self.hass.config_entries.async_update_entry(entry, data=new_data)

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
        now = dt_util.now()
        month_str = now.strftime("%Y-%m-01")
        start_date = (now - timedelta(days=365)).strftime("%Y-%m-%d")
        end_date = now.strftime("%Y-%m-%d")

        # Required
        accounts_data = await self.api.get_accounts(ff_token, wapi_token)

        # Optional
        budgets_data = {}
        try:
            budgets_data = await self.api.get_budgets(ff_token, month_str)
        except Exception as err:  # noqa: BLE001
            LOGGER.warning("Could not fetch budgets data: %s", err)

        # Optional — each wrapped in try/except, logs warning on failure

        inflation_data = None
        try:
            inflation_data = await self.api.get_inflation(
                ff_token, start_date, end_date
            )
        except Exception as err:  # noqa: BLE001
            LOGGER.warning("Could not fetch inflation data: %s", err)

        cashflow_raw = None
        try:
            cashflow_raw = await self.api.get_cashflow_summary(ff_token, month_str)
        except Exception as err:  # noqa: BLE001
            LOGGER.warning("Could not fetch cashflow data: %s", err)

        # Parse cashflow: API returns {periods: [{date, income, expenses, savings}]}
        # Extract current month's period and compute savings rate
        cashflow_data = None
        if isinstance(cashflow_raw, dict):
            periods = cashflow_raw.get("periods", [])
            if periods:
                # Find current month period (month_str = "YYYY-MM-01")
                current = next(
                    (p for p in periods if p.get("date", "").startswith(month_str[:7])),
                    periods[-1],  # fallback to latest
                )
                income = current.get("income", 0) or 0
                expenses = current.get("expenses", 0) or 0
                savings = current.get("savings") or (
                    income + expenses
                )  # expenses are negative
                savings_rate = (
                    round((savings / income) * 100, 1)
                    if income and income > 0
                    else None
                )
                cashflow_data = {
                    "income": income,
                    "expenses": abs(expenses),  # make positive for display
                    "balance": income + expenses,
                    "savings": savings,
                    "savingsRate": savings_rate,
                    "period": current.get("date"),
                    "history": periods[-12:],  # last 12 months for attributes
                }

        transactions_data = None
        all_tx_list: list[dict[str, Any]] = []
        try:
            all_tx_list = await self.api.get_all_transactions(ff_token)
            transactions_data = {
                "totalCount": len(all_tx_list),
                "transactions": all_tx_list,
            }
        except Exception as err:  # noqa: BLE001
            LOGGER.warning("Could not fetch transactions data: %s", err)

        investments_data = None
        try:
            investments_data = await self.api.get_investments(ff_token, wapi_token)
        except InvalidAuthError:
            # Re-raise so the coordinator can refresh tokens and retry
            raise
        except Exception as err:  # noqa: BLE001
            LOGGER.warning("Could not fetch investments data: %s", err)

        exemption_data = None
        try:
            exemption_data = await self.api.get_exemption_orders(
                ff_token, wapi_token=wapi_token
            )
        except Exception as err:  # noqa: BLE001
            LOGGER.warning("Could not fetch exemption orders data: %s", err)

        subscription_data = None
        try:
            subscription_data = await self.api.get_subscription(ff_token)
        except Exception as err:  # noqa: BLE001
            LOGGER.warning("Could not fetch subscription data: %s", err)

        categories_data = None
        try:
            categories_data = await self.api.get_categories(
                ff_token, wapi_token=wapi_token
            )
        except Exception as err:  # noqa: BLE001
            LOGGER.warning("Could not fetch categories data: %s", err)

        # Estimate investment deposits from entire historical transaction history when native investments API is unavailable
        estimated_investment_total = 0.0
        for tx in all_tx_list:
            purpose = str(tx.get("purpose", "")).lower()
            amt = tx.get("amount", 0) or 0
            if (
                "wp.abrechnung" in purpose
                or "isin" in purpose
                or "wertpapier-abrechnung" in purpose
            ):
                estimated_investment_total -= amt

        return {
            "accounts": accounts_data.get("accounts", []),
            "budgets": budgets_data,
            "inflation": inflation_data.get("rows", [])
            if isinstance(inflation_data, dict)
            else [],
            "cashflow": cashflow_data,
            "transactions": transactions_data,
            "investments": investments_data,
            "estimated_investment_total": estimated_investment_total,
            "exemption_orders": exemption_data
            if isinstance(exemption_data, list)
            else [],
            "subscription": subscription_data,
            "categories": categories_data if isinstance(categories_data, list) else [],
        }
