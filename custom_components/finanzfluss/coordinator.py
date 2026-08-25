"""DataUpdateCoordinator for Finanzfluss integration."""

import asyncio
import random
from datetime import datetime, timedelta
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
        if cache and "last_success" in cache:
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
            # 4. Jitter: sleep 5-30s during periodic background updates to avoid concurrent spikes
            if self._last_success is not None and self.data is not None:
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

        # Fetch all independent API endpoints concurrently for instant startup and updates
        accounts_task = self.api.get_accounts(ff_token, wapi_token)
        budgets_task = self.api.get_budgets(ff_token, month_str)
        inflation_task = self.api.get_inflation(ff_token, start_date, end_date)
        cashflow_task = self.api.get_cashflow_summary(ff_token, month_str)
        transactions_task = self.api.get_all_transactions(ff_token)
        investments_task = self.api.get_investments(ff_token, wapi_token)
        exemption_task = self.api.get_exemption_orders(ff_token, wapi_token=wapi_token)
        subscription_task = self.api.get_subscription(ff_token)
        categories_task = self.api.get_categories(ff_token, wapi_token=wapi_token)

        results = await asyncio.gather(
            accounts_task,
            budgets_task,
            inflation_task,
            cashflow_task,
            transactions_task,
            investments_task,
            exemption_task,
            subscription_task,
            categories_task,
            return_exceptions=True,
        )

        (
            accounts_res,
            budgets_res,
            inflation_res,
            cashflow_res,
            transactions_res,
            investments_res,
            exemption_res,
            subscription_res,
            categories_res,
        ) = results

        # Check for invalid auth
        for res in results:
            if isinstance(res, InvalidAuthError):
                raise res

        accounts_data = accounts_res if isinstance(accounts_res, dict) else {}
        budgets_data = budgets_res if isinstance(budgets_res, dict) else {}
        inflation_data = inflation_res if isinstance(inflation_res, dict) else None
        cashflow_raw = cashflow_res if isinstance(cashflow_res, dict) else None
        all_tx_list = transactions_res if isinstance(transactions_res, list) else []
        transactions_data = {
            "totalCount": len(all_tx_list),
            "transactions": all_tx_list,
        }
        investments_data = investments_res if isinstance(investments_res, dict) else None
        exemption_data = exemption_res if isinstance(exemption_res, dict) else None
        subscription_data = subscription_res if isinstance(subscription_res, dict) else None
        categories_data = categories_res if isinstance(categories_res, dict) else None

        # Parse cashflow: API returns {periods: [{date, income, expenses, savings}]}
        # Extract current month's period and compute savings rate
        cashflow_data = None
        if isinstance(cashflow_raw, dict):
            periods = cashflow_raw.get("periods", [])
            if periods:
                current = next(
                    (p for p in periods if p.get("date", "").startswith(month_str[:7])),
                    periods[-1],
                )
                income = current.get("income", 0) or 0
                expenses = current.get("expenses", 0) or 0
                savings = current.get("savings") or (income + expenses)
                savings_rate = (
                    round((savings / income) * 100, 1)
                    if income and income > 0
                    else None
                )
                cashflow_data = {
                    "income": income,
                    "expenses": abs(expenses),
                    "balance": income + expenses,
                    "savings": savings,
                    "savingsRate": savings_rate,
                    "period": current.get("date"),
                    "history": periods[-12:],
                }

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
