"""Sensor platform for Finanzfluss integration."""

from __future__ import annotations

from typing import Any, cast

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import FinanzflussDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Finanzfluss sensor entities based on a config entry."""
    coordinator: FinanzflussDataUpdateCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ]

    entities: list[SensorEntity] = [
        FinanzflussNetWorthSensor(coordinator),
        FinanzflussMonthlyIncomeSensor(coordinator),
        FinanzflussMonthlyExpensesSensor(coordinator),
        FinanzflussMonthlyBalanceSensor(coordinator),
        FinanzflussMonthlySavingsRateSensor(coordinator),
        FinanzflussTransactionCountSensor(coordinator),
        FinanzflussLastTransactionSensor(coordinator),
        FinanzflussInflationSensor(coordinator),
        FinanzflussBudgetTotalSensor(coordinator),
        FinanzflussBudgetSpentSensor(coordinator),
        FinanzflussBudgetRemainingTotalSensor(coordinator),
        FinanzflussSubscriptionSensor(coordinator),
    ]

    # Dynamically create sensors for accounts
    accounts = coordinator.data.get("accounts", [])
    for account in accounts:
        entities.append(FinanzflussAccountSensor(coordinator, account["id"]))

    # Dynamically create sensors for budget buckets
    buckets = coordinator.data.get("budgets", {}).get("buckets", [])
    for bucket in buckets:
        entities.append(FinanzflussBudgetBucketSensor(coordinator, bucket["id"]))
        entities.append(
            FinanzflussBudgetBucketRemainingSensor(coordinator, bucket["id"])
        )

    # Check for Finanzfluss Plus tier (or fallback if investment positions exist)
    sub = coordinator.data.get("subscription") or {}
    has_plus = (
        sub.get("tier") == "plus"
        or sub.get("isActive") is True
        or bool((coordinator.data.get("investments") or {}).get("positions"))
    )

    if has_plus:
        entities.append(FinanzflussInvestmentTotalSensor(coordinator))
        investments = (coordinator.data.get("investments") or {}).get("positions", [])
        for position in investments:
            entities.append(
                FinanzflussInvestmentPositionSensor(coordinator, position["id"])
            )

    exemption_orders = coordinator.data.get("exemption_orders", [])
    for order in exemption_orders:
        entities.append(
            FinanzflussExemptionOrderSensor(
                coordinator, order.get("id") or order.get("bank")
            )
        )

    async_add_entities(entities)


class FinanzflussBaseEntity(
    CoordinatorEntity[FinanzflussDataUpdateCoordinator], SensorEntity
):
    """Base class for all Finanzfluss entities sharing device registration."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: FinanzflussDataUpdateCoordinator, entry_id: str | None = None
    ) -> None:
        """Initialize the base entity."""
        super().__init__(coordinator)
        if entry_id is None:
            entry_id = (
                coordinator.config_entry.entry_id if coordinator.config_entry else ""
            )
        self._entry_id = entry_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name="Finanzfluss Copilot",
            manufacturer="Finflow GmbH",
            model="Finanzfluss Copilot Dashboard",
            configuration_url="https://www.finanzfluss.de/user",
        )


class FinanzflussAccountSensor(FinanzflussBaseEntity):
    """Representation of a Finanzfluss Account Sensor."""

    def __init__(
        self, coordinator: FinanzflussDataUpdateCoordinator, account_id: int
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._account_id = account_id
        self._attr_unique_id = f"finanzfluss_account_{account_id}"
        self._attr_device_class = SensorDeviceClass.MONETARY
        self._attr_state_class = SensorStateClass.TOTAL

    @property
    def _account(self) -> dict[str, Any] | None:
        for account in self.coordinator.data.get("accounts", []):
            if account["id"] == self._account_id:
                return cast(dict[str, Any], account)
        return None

    @property
    def name(self) -> str | None:
        """Return the name of the sensor."""
        account = self._account
        if account:
            return f"Account {account.get('name', '')}"
        return f"Account {self._account_id}"

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        account = self._account
        if not account:
            return None
        val = account.get("balance")
        if (val is None or val == 0) and account.get("type") == "01_depot":
            val = (
                account.get("marketValue")
                or account.get("portfolioValue")
                or account.get("totalValue")
                or account.get("currentValue")
                or account.get("value")
                or 0.0
            )
        return cast(float | None, val)

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit of measurement."""
        account = self._account
        return account.get("currency", "EUR") if account else "EUR"

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes."""
        account = self._account
        if not account:
            return None
        attrs: dict[str, Any] = {
            "id": account.get("id"),
            "type": account.get("type"),
            "bank_name": account.get("bankName"),
            "iban": account.get("iban"),
            "is_hidden": account.get("isHidden"),
            "last_sync": account.get("lastSync"),
            "bank_connection_type": account.get("bankConnectionType"),
        }
        # Aggregate holdings details inside the depot account entity to avoid entity spam
        if account.get("type") == "01_depot":
            investments = self.coordinator.data.get("investments") or {}
            positions = investments.get("positions", [])
            depot_positions = []
            total_gain = 0.0
            total_purchase = 0.0
            for p in positions:
                # Map investments referencing this depot account ID
                # (some API endpoints link via accountId)
                if p.get("accountId") == self._account_id or str(
                    p.get("accountId")
                ) == str(self._account_id):
                    depot_positions.append(
                        {
                            "name": p.get("name"),
                            "isin": p.get("isin"),
                            "quantity": p.get("quantity"),
                            "market_value": p.get("marketValue"),
                            "purchase_value": p.get("purchaseValue"),
                            "gain": p.get("gain"),
                            "gain_percent": p.get("gainPercent"),
                        }
                    )
                    total_gain += p.get("gain", 0) or 0
                    total_purchase += p.get("purchaseValue", 0) or 0

            if depot_positions:
                attrs["positions"] = depot_positions
                attrs["total_gain"] = total_gain
                attrs["total_purchase_value"] = total_purchase
                if total_purchase > 0:
                    attrs["total_gain_percent"] = round(
                        (total_gain / total_purchase) * 100, 2
                    )
        return attrs


class FinanzflussNetWorthSensor(FinanzflussBaseEntity):
    """Representation of a Finanzfluss Net Worth (Gesamtvermögen) Sensor."""

    def __init__(self, coordinator: FinanzflussDataUpdateCoordinator) -> None:
        """Initialize the sensor."""
        entry_id = coordinator.config_entry.entry_id if coordinator.config_entry else ""
        super().__init__(coordinator, entry_id)
        self._attr_unique_id = f"finanzfluss_net_worth_{entry_id}"
        self._attr_translation_key = "net_worth"
        self._attr_device_class = SensorDeviceClass.MONETARY
        self._attr_state_class = SensorStateClass.TOTAL
        self._attr_native_unit_of_measurement = "EUR"

    @property
    def native_value(self) -> float | None:
        """Calculate total net worth: accounts balance + investments totalValue (if not already included in accounts)."""
        accounts = self.coordinator.data.get("accounts", [])

        total_accounts = 0.0
        has_depot_account = False

        for account in accounts:
            if account.get("isHidden"):
                continue
            acc_type = account.get("type")
            balance = account.get("balance") or 0.0

            if acc_type == "01_depot":
                has_depot_account = True
                if balance == 0:
                    balance = (
                        account.get("marketValue")
                        or account.get("portfolioValue")
                        or account.get("totalValue")
                        or account.get("currentValue")
                        or account.get("value")
                        or 0.0
                    )
            total_accounts += balance

        investments_total = 0.0
        investments_data = self.coordinator.data.get("investments")
        if investments_data and isinstance(investments_data, dict):
            investments_total = investments_data.get("totalValue") or sum(
                p.get("marketValue", 0) for p in investments_data.get("positions", [])
            )

        # Check for active Plus subscription
        sub = self.coordinator.data.get("subscription") or {}
        has_plus = (
            sub.get("tier") == "plus"
            or sub.get("isActive") is True
            or (investments_data is not None and bool(investments_total))
        )

        if has_plus:
            # Native behavior: Add native investments totalValue if provided
            return float(total_accounts + investments_total)

        # Fallback behavior (No Plus subscription): Add estimated investment transactions sum
        tx_est = self.coordinator.data.get("estimated_investment_total", 0.0)
        return float(total_accounts + tx_est)




    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return rich breakdown and analytics attributes."""
        accounts = self.coordinator.data.get("accounts", [])
        investments_data = self.coordinator.data.get("investments")
        transactions_data = self.coordinator.data.get("transactions") or {}

        cash_total = sum(
            a.get("balance", 0) or 0
            for a in accounts
            if not a.get("isHidden") and a.get("type") != "01_depot"
        )

        inv_total = 0.0
        if investments_data and isinstance(investments_data, dict):
            inv_total = investments_data.get("totalValue") or sum(
                p.get("marketValue", 0) for p in investments_data.get("positions", [])
            )
        if inv_total == 0:
            inv_total = self.coordinator.data.get("estimated_investment_total", 0.0)

        # Analyze transactions for dividends, interest, and gains
        dividends_total = 0.0
        interest_total = 0.0
        realized_gains = 0.0

        tx_list = transactions_data.get("transactions", []) if isinstance(transactions_data, dict) else []
        for tx in tx_list:
            purpose = str(tx.get("purpose", "")).lower()
            name = str(tx.get("name", "")).lower()
            amt = tx.get("amount", 0) or 0

            if amt > 0:
                if any(k in purpose or k in name for k in ("dividende", "ausschüttung", "coupon")):
                    dividends_total += amt
                elif any(k in purpose or k in name for k in ("zins", "zinsen", "zinsgutschrift")):
                    interest_total += amt
                elif any(k in purpose or k in name for k in ("gewinn", "ertrag", "verkauf")):
                    realized_gains += amt

        sub = self.coordinator.data.get("subscription") or {}

        attrs: dict[str, Any] = {
            "cash_total": round(cash_total, 2),
            "investments_total": round(inv_total, 2),
            "allocation": {
                "cash": round(cash_total, 2),
                "investments": round(inv_total, 2),
            },
            "dividends_total": round(dividends_total, 2),
            "interest_total": round(interest_total, 2),
            "realized_gains_total": round(realized_gains, 2),
            "total_income_gains": round(dividends_total + interest_total + realized_gains, 2),
            "subscription_tier": sub.get("tier", "free"),
            "account_count": len(accounts),
            "accounts": [
                {
                    "id": a.get("id"),
                    "name": a.get("name"),
                    "type": a.get("type"),
                    "balance": a.get("balance"),
                    "currency": a.get("currency"),
                }
                for a in accounts
            ],
        }
        return attrs



class FinanzflussInflationSensor(FinanzflussBaseEntity):
    """Representation of a Finanzfluss Inflation Rate Sensor."""

    # Unimportant entity -> disabled by default
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: FinanzflussDataUpdateCoordinator) -> None:
        """Initialize the sensor."""
        entry_id = coordinator.config_entry.entry_id if coordinator.config_entry else ""
        super().__init__(coordinator, entry_id)
        self._attr_unique_id = f"finanzfluss_inflation_{entry_id}"
        self._attr_translation_key = "inflation_rate"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = "%"

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        default_val = None
        rows = self.coordinator.data.get("inflation", [])
        if rows:
            return cast(float | None, rows[-1].get("inflationRate"))
        return default_val

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes."""
        rows = self.coordinator.data.get("inflation", [])
        if rows:
            last = rows[-1]
            return {
                "date": last.get("date"),
                "consumer_price_index": last.get("consumerPriceIndex"),
                "history": rows,
            }
        return None


class FinanzflussBudgetTotalSensor(FinanzflussBaseEntity):
    """Representation of a Finanzfluss Budget Total Limit Sensor."""

    # Unimportant entity -> disabled by default
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: FinanzflussDataUpdateCoordinator) -> None:
        """Initialize the sensor."""
        entry_id = coordinator.config_entry.entry_id if coordinator.config_entry else ""
        super().__init__(coordinator, entry_id)
        self._attr_unique_id = f"finanzfluss_budget_total_{entry_id}"
        self._attr_translation_key = "budget_total"
        self._attr_device_class = SensorDeviceClass.MONETARY
        self._attr_native_unit_of_measurement = "EUR"

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        budgets = self.coordinator.data.get("budgets", {})
        if budgets:
            return cast(float | None, budgets.get("totals", {}).get("amount"))
        return None


class FinanzflussBudgetSpentSensor(FinanzflussBaseEntity):
    """Representation of a Finanzfluss Budget Total Spent Sensor."""

    # Unimportant entity -> disabled by default
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: FinanzflussDataUpdateCoordinator) -> None:
        """Initialize the sensor."""
        entry_id = coordinator.config_entry.entry_id if coordinator.config_entry else ""
        super().__init__(coordinator, entry_id)
        self._attr_unique_id = f"finanzfluss_budget_spent_{entry_id}"
        self._attr_translation_key = "budget_spent"
        self._attr_device_class = SensorDeviceClass.MONETARY
        self._attr_state_class = SensorStateClass.TOTAL
        self._attr_native_unit_of_measurement = "EUR"

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        budgets = self.coordinator.data.get("budgets", {})
        if budgets:
            return cast(float | None, budgets.get("totals", {}).get("spent"))
        return None


class FinanzflussBudgetRemainingTotalSensor(FinanzflussBaseEntity):
    """Representation of a Finanzfluss Budget Remaining Sensor."""

    def __init__(self, coordinator: FinanzflussDataUpdateCoordinator) -> None:
        """Initialize the sensor."""
        entry_id = coordinator.config_entry.entry_id if coordinator.config_entry else ""
        super().__init__(coordinator, entry_id)
        self._attr_unique_id = f"finanzfluss_budget_remaining_{entry_id}"
        self._attr_translation_key = "budget_remaining"
        self._attr_device_class = SensorDeviceClass.MONETARY
        self._attr_state_class = SensorStateClass.TOTAL
        self._attr_native_unit_of_measurement = "EUR"

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        budgets = self.coordinator.data.get("budgets", {})
        if budgets:
            totals = budgets.get("totals", {})
            amount = totals.get("amount") or 0
            spent = totals.get("spent") or 0
            return float(amount - spent)
        return None


class FinanzflussBudgetBucketSensor(FinanzflussBaseEntity):
    """Representation of a Finanzfluss Budget Bucket Sensor."""

    def __init__(
        self, coordinator: FinanzflussDataUpdateCoordinator, bucket_id: int
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._bucket_id = bucket_id
        self._attr_unique_id = f"finanzfluss_budget_bucket_{bucket_id}"
        self._attr_device_class = SensorDeviceClass.MONETARY
        self._attr_state_class = SensorStateClass.TOTAL
        self._attr_native_unit_of_measurement = "EUR"

    @property
    def _bucket(self) -> dict[str, Any] | None:
        buckets = self.coordinator.data.get("budgets", {}).get("buckets", [])
        for bucket in buckets:
            if bucket["id"] == self._bucket_id:
                return cast(dict[str, Any], bucket)
        return None

    @property
    def name(self) -> str | None:
        """Return the name of the sensor."""
        bucket = self._bucket
        if bucket:
            return f"Budget {bucket.get('title', '')}"
        return f"Budget {self._bucket_id}"

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        bucket = self._bucket
        return cast(float | None, bucket.get("spent")) if bucket else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes."""
        bucket = self._bucket
        if not bucket:
            return None
        return {
            "id": bucket.get("id"),
            "limit": bucket.get("amount"),
            "category_slug": bucket.get("categorySlug"),
            "color": bucket.get("color"),
        }


class FinanzflussBudgetBucketRemainingSensor(FinanzflussBaseEntity):
    """Representation of a Finanzfluss Budget Bucket Remaining Sensor."""

    # Secondary budget entity -> disabled by default
    _attr_entity_registry_enabled_default = False

    def __init__(
        self, coordinator: FinanzflussDataUpdateCoordinator, bucket_id: int
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._bucket_id = bucket_id
        self._attr_unique_id = f"finanzfluss_budget_bucket_remaining_{bucket_id}"
        self._attr_device_class = SensorDeviceClass.MONETARY
        self._attr_state_class = SensorStateClass.TOTAL
        self._attr_native_unit_of_measurement = "EUR"

    @property
    def _bucket(self) -> dict[str, Any] | None:
        buckets = self.coordinator.data.get("budgets", {}).get("buckets", [])
        for bucket in buckets:
            if bucket["id"] == self._bucket_id:
                return cast(dict[str, Any], bucket)
        return None

    @property
    def name(self) -> str | None:
        """Return the name of the sensor."""
        bucket = self._bucket
        if bucket:
            return f"Budget {bucket.get('title', '')} Remaining"
        return f"Budget Remaining {self._bucket_id}"

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        bucket = self._bucket
        if bucket:
            amount = bucket.get("amount") or 0
            spent = bucket.get("spent") or 0
            return float(amount - spent)
        return None


class FinanzflussMonthlyIncomeSensor(FinanzflussBaseEntity):
    """Representation of a Finanzfluss Monthly Income Sensor."""

    def __init__(self, coordinator: FinanzflussDataUpdateCoordinator) -> None:
        """Initialize the sensor."""
        entry_id = coordinator.config_entry.entry_id if coordinator.config_entry else ""
        super().__init__(coordinator, entry_id)
        self._attr_unique_id = f"finanzfluss_monthly_income_{entry_id}"
        self._attr_translation_key = "monthly_income"
        self._attr_device_class = SensorDeviceClass.MONETARY
        self._attr_state_class = SensorStateClass.TOTAL
        self._attr_native_unit_of_measurement = "EUR"

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        cashflow = self.coordinator.data.get("cashflow")
        if cashflow:
            return cast(float | None, cashflow.get("income"))
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Merge categories and cashflow history into income attributes."""
        cashflow = self.coordinator.data.get("cashflow") or {}
        return {
            "period": cashflow.get("period"),
            "history": cashflow.get("history", []),
            "categories": self.coordinator.data.get("categories", []),
        }


class FinanzflussMonthlyExpensesSensor(FinanzflussBaseEntity):
    """Representation of a Finanzfluss Monthly Expenses Sensor."""

    def __init__(self, coordinator: FinanzflussDataUpdateCoordinator) -> None:
        """Initialize the sensor."""
        entry_id = coordinator.config_entry.entry_id if coordinator.config_entry else ""
        super().__init__(coordinator, entry_id)
        self._attr_unique_id = f"finanzfluss_monthly_expenses_{entry_id}"
        self._attr_translation_key = "monthly_expenses"
        self._attr_device_class = SensorDeviceClass.MONETARY
        self._attr_state_class = SensorStateClass.TOTAL
        self._attr_native_unit_of_measurement = "EUR"

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        cashflow = self.coordinator.data.get("cashflow")
        if cashflow:
            return cast(float | None, cashflow.get("expenses"))
        return None


class FinanzflussMonthlyBalanceSensor(FinanzflussBaseEntity):
    """Representation of a Finanzfluss Monthly Balance Sensor."""

    def __init__(self, coordinator: FinanzflussDataUpdateCoordinator) -> None:
        """Initialize the sensor."""
        entry_id = coordinator.config_entry.entry_id if coordinator.config_entry else ""
        super().__init__(coordinator, entry_id)
        self._attr_unique_id = f"finanzfluss_monthly_balance_{entry_id}"
        self._attr_translation_key = "monthly_balance"
        self._attr_device_class = SensorDeviceClass.MONETARY
        self._attr_state_class = SensorStateClass.TOTAL
        self._attr_native_unit_of_measurement = "EUR"

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        cashflow = self.coordinator.data.get("cashflow")
        if cashflow:
            if "balance" in cashflow:
                return cast(float | None, cashflow["balance"])
            if "income" in cashflow and "expenses" in cashflow:
                return cast(float | None, cashflow["income"] - cashflow["expenses"])
        return None


class FinanzflussMonthlySavingsRateSensor(FinanzflussBaseEntity):
    """Representation of a Finanzfluss Monthly Savings Rate Sensor."""

    def __init__(self, coordinator: FinanzflussDataUpdateCoordinator) -> None:
        """Initialize the sensor."""
        entry_id = coordinator.config_entry.entry_id if coordinator.config_entry else ""
        super().__init__(coordinator, entry_id)
        self._attr_unique_id = f"finanzfluss_savings_rate_{entry_id}"
        self._attr_translation_key = "savings_rate"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = "%"

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        cashflow = self.coordinator.data.get("cashflow")
        if cashflow:
            return cast(float | None, cashflow.get("savingsRate"))
        return None


class FinanzflussTransactionCountSensor(FinanzflussBaseEntity):
    """Representation of a Finanzfluss Transaction Count Sensor."""

    # Unimportant entity -> disabled by default
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: FinanzflussDataUpdateCoordinator) -> None:
        """Initialize the sensor."""
        entry_id = coordinator.config_entry.entry_id if coordinator.config_entry else ""
        super().__init__(coordinator, entry_id)
        self._attr_unique_id = f"finanzfluss_transaction_count_{entry_id}"
        self._attr_translation_key = "transaction_count"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = None

    @property
    def native_value(self) -> int | None:
        """Return the state of the sensor."""
        transactions = self.coordinator.data.get("transactions")
        if transactions:
            return cast(
                int | None,
                transactions.get("totalCount")
                or len(transactions.get("transactions", [])),
            )
        return None


class FinanzflussLastTransactionSensor(FinanzflussBaseEntity):
    """Representation of a Finanzfluss Last Transaction Sensor."""

    # Unimportant entity -> disabled by default
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: FinanzflussDataUpdateCoordinator) -> None:
        """Initialize the sensor."""
        entry_id = coordinator.config_entry.entry_id if coordinator.config_entry else ""
        super().__init__(coordinator, entry_id)
        self._attr_unique_id = f"finanzfluss_last_transaction_{entry_id}"
        self._attr_translation_key = "last_transaction"
        self._attr_device_class = SensorDeviceClass.MONETARY
        self._attr_state_class = SensorStateClass.TOTAL
        self._attr_native_unit_of_measurement = "EUR"

    @property
    def _first_transaction(self) -> dict[str, Any] | None:
        transactions = self.coordinator.data.get("transactions")
        if transactions:
            txs = transactions.get("transactions", [])
            if txs:
                return cast(dict[str, Any], txs[0])
        return None

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        tx = self._first_transaction
        if tx:
            return cast(float | None, tx.get("amount"))
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes."""
        tx = self._first_transaction
        if not tx:
            return None
        return {
            "date": tx.get("date"),
            "description": tx.get("description"),
            "category_slug": tx.get("categorySlug"),
            "account_id": tx.get("accountId"),
        }


class FinanzflussInvestmentTotalSensor(FinanzflussBaseEntity):
    """Representation of a Finanzfluss Total Investments Sensor."""

    def __init__(self, coordinator: FinanzflussDataUpdateCoordinator) -> None:
        """Initialize the sensor."""
        entry_id = coordinator.config_entry.entry_id if coordinator.config_entry else ""
        super().__init__(coordinator, entry_id)
        self._attr_unique_id = f"finanzfluss_investment_total_{entry_id}"
        self._attr_translation_key = "investment_total"
        self._attr_device_class = SensorDeviceClass.MONETARY
        self._attr_state_class = SensorStateClass.TOTAL
        self._attr_native_unit_of_measurement = "EUR"

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        investments = self.coordinator.data.get("investments")
        if investments:
            return cast(
                float | None,
                investments.get("totalValue")
                or sum(
                    p.get("marketValue", 0) for p in investments.get("positions", [])
                ),
            )
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes."""
        investments = self.coordinator.data.get("investments")
        if not investments:
            return None

        # Calculate totals from positions if not present at root
        positions = investments.get("positions", [])
        total_gain = sum(p.get("gain", 0) or 0 for p in positions)
        total_purchase = sum(p.get("purchaseValue", 0) or 0 for p in positions)

        attrs = {
            "total_gain": total_gain,
            "total_purchase_value": total_purchase,
        }
        if total_purchase > 0:
            attrs["total_gain_percent"] = round((total_gain / total_purchase) * 100, 2)

        return attrs


class FinanzflussInvestmentPositionSensor(FinanzflussBaseEntity):
    """Representation of a Finanzfluss Investment Position Sensor."""

    def __init__(
        self, coordinator: FinanzflussDataUpdateCoordinator, position_id: int
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._position_id = position_id
        self._attr_unique_id = f"finanzfluss_investment_position_{position_id}"
        self._attr_device_class = SensorDeviceClass.MONETARY
        self._attr_state_class = SensorStateClass.TOTAL
        self._attr_native_unit_of_measurement = "EUR"

    @property
    def _position(self) -> dict[str, Any] | None:
        investments = self.coordinator.data.get("investments")
        if investments:
            positions = investments.get("positions", [])
            for p in positions:
                if p["id"] == self._position_id:
                    return cast(dict[str, Any], p)
        return None

    @property
    def name(self) -> str | None:
        """Return the name of the sensor."""
        position = self._position
        if position:
            return f"Investment {position.get('name', '')}"
        return f"Investment {self._position_id}"

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        position = self._position
        return cast(float | None, position.get("marketValue")) if position else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes."""
        position = self._position
        if not position:
            return None
        return {
            "name": position.get("name"),
            "isin": position.get("isin"),
            "quantity": position.get("quantity"),
            "purchase_value": position.get("purchaseValue"),
            "gain": position.get("gain"),
            "gain_percent": position.get("gainPercent"),
        }


class FinanzflussExemptionOrderSensor(FinanzflussBaseEntity):
    """Representation of a Finanzfluss Exemption Order Sensor."""

    def __init__(
        self, coordinator: FinanzflussDataUpdateCoordinator, order_id: int | str
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._order_id = order_id
        self._attr_unique_id = f"finanzfluss_exemption_order_{order_id}"
        self._attr_device_class = SensorDeviceClass.MONETARY
        self._attr_state_class = SensorStateClass.TOTAL
        self._attr_native_unit_of_measurement = "EUR"

    @property
    def _order(self) -> dict[str, Any] | None:
        orders = self.coordinator.data.get("exemption_orders", [])
        for order in orders:
            if order.get("id") == self._order_id or order.get("bank") == self._order_id:
                return cast(dict[str, Any], order)
        return None

    @property
    def name(self) -> str | None:
        """Return the name of the sensor."""
        order = self._order
        if order:
            return f"Exemption Order {order.get('bank', self._order_id)}"
        return f"Exemption Order {self._order_id}"

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        order = self._order
        if order:
            allocated = order.get("allocatedAmount") or 0
            used = order.get("usedAmount") or 0
            return float(allocated - used)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes."""
        order = self._order
        if not order:
            return None
        return {
            "bank": order.get("bank"),
            "allocated_amount": order.get("allocatedAmount"),
            "used_amount": order.get("usedAmount"),
            "year": order.get("year"),
        }


class FinanzflussSubscriptionSensor(FinanzflussBaseEntity):
    """Representation of a Finanzfluss Subscription Sensor."""

    # Spam prevention: disabled by default since details are now on the main Net Worth sensor attributes
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: FinanzflussDataUpdateCoordinator) -> None:
        """Initialize the sensor."""
        entry_id = coordinator.config_entry.entry_id if coordinator.config_entry else ""
        super().__init__(coordinator, entry_id)
        self._attr_unique_id = f"finanzfluss_subscription_{entry_id}"
        self._attr_translation_key = "subscription"

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        subscription = self.coordinator.data.get("subscription")
        if subscription:
            return cast(str | None, subscription.get("tier"))
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes."""
        subscription = self.coordinator.data.get("subscription")
        if not subscription:
            return None
        return {
            "is_active": subscription.get("isActive"),
        }
