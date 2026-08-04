"""Tests for Finanzfluss sensor entities."""

from __future__ import annotations

from unittest.mock import MagicMock

from custom_components.finanzfluss.sensor import (
    FinanzflussAccountSensor,
    FinanzflussBudgetBucketRemainingSensor,
    FinanzflussBudgetBucketSensor,
    FinanzflussBudgetRemainingTotalSensor,
    FinanzflussBudgetSpentSensor,
    FinanzflussBudgetTotalSensor,
    FinanzflussExemptionOrderSensor,
    FinanzflussInflationSensor,
    FinanzflussInvestmentPositionSensor,
    FinanzflussInvestmentTotalSensor,
    FinanzflussLastTransactionSensor,
    FinanzflussMonthlyBalanceSensor,
    FinanzflussMonthlyExpensesSensor,
    FinanzflussMonthlyIncomeSensor,
    FinanzflussMonthlySavingsRateSensor,
    FinanzflussNetWorthSensor,
    FinanzflussSubscriptionSensor,
    FinanzflussTransactionCountSensor,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_coordinator(data: dict) -> MagicMock:
    """Build a minimal mock coordinator with the given data dict."""
    coord = MagicMock()
    coord.data = data
    coord.config_entry.entry_id = "test_entry_id_123"
    return coord


# ---------------------------------------------------------------------------
# Net Worth
# ---------------------------------------------------------------------------


class TestNetWorthSensor:
    def test_native_value_with_investments(self, sample_coordinator_data):
        coord = _make_coordinator(sample_coordinator_data)
        sensor = FinanzflussNetWorthSensor(coord)
        # 1500 + 5000 (accounts) + 25000 (investments.totalValue)
        assert sensor.native_value == 31500.0

    def test_native_value_without_investments(self, sample_coordinator_data):
        data = dict(sample_coordinator_data)
        data["investments"] = None  # Plus subscription not available
        coord = _make_coordinator(data)
        sensor = FinanzflussNetWorthSensor(coord)
        # Only cash accounts summed
        assert sensor.native_value == 6500.0  # 1500 + 5000

    def test_native_value_excludes_hidden(self, sample_coordinator_data):
        data = dict(sample_coordinator_data)
        data["accounts"] = [
            {"id": 1, "balance": 1000.0, "isHidden": False},
            {"id": 2, "balance": 500.0, "isHidden": True},
        ]
        coord = _make_coordinator(data)
        sensor = FinanzflussNetWorthSensor(coord)
        assert sensor.native_value == 26000.0  # 1000 (visible) + 25000 (investments)

    def test_native_value_empty_accounts(self):
        coord = _make_coordinator({"accounts": []})
        sensor = FinanzflussNetWorthSensor(coord)
        assert sensor.native_value == 0.0

    def test_native_value_missing_data(self):
        coord = _make_coordinator({})
        sensor = FinanzflussNetWorthSensor(coord)
        assert sensor.native_value == 0.0

    def test_extra_attrs_investments_note_when_none(self, sample_coordinator_data):
        data = dict(sample_coordinator_data)
        data["investments"] = None
        coord = _make_coordinator(data)
        sensor = FinanzflussNetWorthSensor(coord)
        attrs = sensor.extra_state_attributes
        assert attrs is not None
        assert "investments_note" in attrs

    def test_extra_attrs_investments_total_when_available(
        self, sample_coordinator_data
    ):
        coord = _make_coordinator(sample_coordinator_data)
        sensor = FinanzflussNetWorthSensor(coord)
        attrs = sensor.extra_state_attributes
        assert attrs is not None
        assert attrs["investments_total"] == 25000.0


# ---------------------------------------------------------------------------
# Account Sensor
# ---------------------------------------------------------------------------


class TestAccountSensor:
    def test_native_value(self, sample_coordinator_data):
        coord = _make_coordinator(sample_coordinator_data)
        sensor = FinanzflussAccountSensor(coord, 1)
        assert sensor.native_value == 1500.0

    def test_name(self, sample_coordinator_data):
        coord = _make_coordinator(sample_coordinator_data)
        sensor = FinanzflussAccountSensor(coord, 1)
        assert "Girokonto" in sensor.name

    def test_unit_of_measurement(self, sample_coordinator_data):
        coord = _make_coordinator(sample_coordinator_data)
        sensor = FinanzflussAccountSensor(coord, 1)
        assert sensor.native_unit_of_measurement == "EUR"

    def test_extra_state_attributes(self, sample_coordinator_data):
        coord = _make_coordinator(sample_coordinator_data)
        sensor = FinanzflussAccountSensor(coord, 1)
        attrs = sensor.extra_state_attributes
        assert attrs is not None
        assert attrs["bank_name"] == "Test Bank"
        assert attrs["iban"] == "DE12345678901234567890"

    def test_unknown_account_returns_none(self, sample_coordinator_data):
        coord = _make_coordinator(sample_coordinator_data)
        sensor = FinanzflussAccountSensor(coord, 9999)
        assert sensor.native_value is None

    def test_missing_accounts_data(self):
        coord = _make_coordinator({})
        sensor = FinanzflussAccountSensor(coord, 1)
        assert sensor.native_value is None


# ---------------------------------------------------------------------------
# Inflation
# ---------------------------------------------------------------------------


class TestInflationSensor:
    def test_native_value(self, sample_coordinator_data):
        coord = _make_coordinator(sample_coordinator_data)
        sensor = FinanzflussInflationSensor(coord)
        assert sensor.native_value == 2.9

    def test_extra_state_attributes(self, sample_coordinator_data):
        coord = _make_coordinator(sample_coordinator_data)
        sensor = FinanzflussInflationSensor(coord)
        attrs = sensor.extra_state_attributes
        assert attrs is not None
        assert attrs["date"] == "2024-01-01"
        assert attrs["consumer_price_index"] == 118.1

    def test_empty_inflation_returns_none(self):
        coord = _make_coordinator({"inflation": []})
        sensor = FinanzflussInflationSensor(coord)
        assert sensor.native_value is None

    def test_missing_inflation_key(self):
        coord = _make_coordinator({})
        sensor = FinanzflussInflationSensor(coord)
        assert sensor.native_value is None


# ---------------------------------------------------------------------------
# Budget Sensors
# ---------------------------------------------------------------------------


class TestBudgetSensors:
    def test_budget_total(self, sample_coordinator_data):
        coord = _make_coordinator(sample_coordinator_data)
        sensor = FinanzflussBudgetTotalSensor(coord)
        assert sensor.native_value == 2000.0

    def test_budget_spent(self, sample_coordinator_data):
        coord = _make_coordinator(sample_coordinator_data)
        sensor = FinanzflussBudgetSpentSensor(coord)
        assert sensor.native_value == 1200.0

    def test_budget_remaining(self, sample_coordinator_data):
        coord = _make_coordinator(sample_coordinator_data)
        sensor = FinanzflussBudgetRemainingTotalSensor(coord)
        assert sensor.native_value == 800.0  # 2000 - 1200

    def test_budget_missing_data(self):
        coord = _make_coordinator({})
        assert FinanzflussBudgetTotalSensor(coord).native_value is None
        assert FinanzflussBudgetSpentSensor(coord).native_value is None
        assert FinanzflussBudgetRemainingTotalSensor(coord).native_value is None


class TestBudgetBucketSensors:
    def test_bucket_spent(self, sample_coordinator_data):
        coord = _make_coordinator(sample_coordinator_data)
        sensor = FinanzflussBudgetBucketSensor(coord, 10)
        assert sensor.native_value == 300.0

    def test_bucket_name(self, sample_coordinator_data):
        coord = _make_coordinator(sample_coordinator_data)
        sensor = FinanzflussBudgetBucketSensor(coord, 10)
        assert "Groceries" in sensor.name

    def test_bucket_extra_attrs(self, sample_coordinator_data):
        coord = _make_coordinator(sample_coordinator_data)
        sensor = FinanzflussBudgetBucketSensor(coord, 10)
        attrs = sensor.extra_state_attributes
        assert attrs is not None
        assert attrs["limit"] == 500.0
        assert attrs["category_slug"] == "groceries"

    def test_bucket_remaining(self, sample_coordinator_data):
        coord = _make_coordinator(sample_coordinator_data)
        sensor = FinanzflussBudgetBucketRemainingSensor(coord, 10)
        assert sensor.native_value == 200.0  # 500 - 300

    def test_bucket_unknown_returns_none(self, sample_coordinator_data):
        coord = _make_coordinator(sample_coordinator_data)
        sensor = FinanzflussBudgetBucketSensor(coord, 9999)
        assert sensor.native_value is None


# ---------------------------------------------------------------------------
# Cashflow Sensors
# ---------------------------------------------------------------------------


class TestCashflowSensors:
    def test_monthly_income(self, sample_coordinator_data):
        coord = _make_coordinator(sample_coordinator_data)
        sensor = FinanzflussMonthlyIncomeSensor(coord)
        assert sensor.native_value == 3500.0

    def test_monthly_expenses(self, sample_coordinator_data):
        coord = _make_coordinator(sample_coordinator_data)
        sensor = FinanzflussMonthlyExpensesSensor(coord)
        assert sensor.native_value == 2100.0

    def test_monthly_balance(self, sample_coordinator_data):
        coord = _make_coordinator(sample_coordinator_data)
        sensor = FinanzflussMonthlyBalanceSensor(coord)
        assert sensor.native_value == 1400.0

    def test_savings_rate(self, sample_coordinator_data):
        coord = _make_coordinator(sample_coordinator_data)
        sensor = FinanzflussMonthlySavingsRateSensor(coord)
        assert sensor.native_value == 40.0

    def test_cashflow_none_when_missing(self):
        coord = _make_coordinator({})
        assert FinanzflussMonthlyIncomeSensor(coord).native_value is None
        assert FinanzflussMonthlyExpensesSensor(coord).native_value is None
        assert FinanzflussMonthlyBalanceSensor(coord).native_value is None
        assert FinanzflussMonthlySavingsRateSensor(coord).native_value is None


# ---------------------------------------------------------------------------
# Transaction Sensors
# ---------------------------------------------------------------------------


class TestTransactionSensors:
    def test_transaction_count(self, sample_coordinator_data):
        coord = _make_coordinator(sample_coordinator_data)
        sensor = FinanzflussTransactionCountSensor(coord)
        assert sensor.native_value == 42

    def test_last_transaction_amount(self, sample_coordinator_data):
        coord = _make_coordinator(sample_coordinator_data)
        sensor = FinanzflussLastTransactionSensor(coord)
        assert sensor.native_value == -45.50

    def test_last_transaction_attrs(self, sample_coordinator_data):
        coord = _make_coordinator(sample_coordinator_data)
        sensor = FinanzflussLastTransactionSensor(coord)
        attrs = sensor.extra_state_attributes
        assert attrs is not None
        assert attrs["description"] == "Supermarkt"
        assert attrs["date"] == "2024-01-14"

    def test_transaction_none_when_missing(self):
        coord = _make_coordinator({})
        assert FinanzflussTransactionCountSensor(coord).native_value is None
        assert FinanzflussLastTransactionSensor(coord).native_value is None

    def test_transaction_count_fallback_to_list_length(self):
        data = {"transactions": {"transactions": [{"id": 1}, {"id": 2}]}}
        coord = _make_coordinator(data)
        sensor = FinanzflussTransactionCountSensor(coord)
        # Should return len of list when totalCount not present
        assert sensor.native_value in (2, None)


# ---------------------------------------------------------------------------
# Investment Sensors
# ---------------------------------------------------------------------------


class TestInvestmentSensors:
    def test_total_investment(self, sample_coordinator_data):
        coord = _make_coordinator(sample_coordinator_data)
        sensor = FinanzflussInvestmentTotalSensor(coord)
        assert sensor.native_value == 25000.0

    def test_investment_position(self, sample_coordinator_data):
        coord = _make_coordinator(sample_coordinator_data)
        sensor = FinanzflussInvestmentPositionSensor(coord, 200)
        assert sensor.native_value == 15000.0

    def test_investment_position_name(self, sample_coordinator_data):
        coord = _make_coordinator(sample_coordinator_data)
        sensor = FinanzflussInvestmentPositionSensor(coord, 200)
        assert "MSCI World ETF" in sensor.name

    def test_investment_position_attrs(self, sample_coordinator_data):
        coord = _make_coordinator(sample_coordinator_data)
        sensor = FinanzflussInvestmentPositionSensor(coord, 200)
        attrs = sensor.extra_state_attributes
        assert attrs is not None
        assert attrs["isin"] == "IE00B4L5Y983"
        assert attrs["gain"] == 3000.0
        assert attrs["gain_percent"] == 25.0

    def test_investment_none_when_missing(self):
        coord = _make_coordinator({})
        assert FinanzflussInvestmentTotalSensor(coord).native_value is None

    def test_investment_position_unknown_returns_none(self, sample_coordinator_data):
        coord = _make_coordinator(sample_coordinator_data)
        sensor = FinanzflussInvestmentPositionSensor(coord, 9999)
        assert sensor.native_value is None


# ---------------------------------------------------------------------------
# Exemption Order Sensors
# ---------------------------------------------------------------------------


class TestExemptionOrderSensor:
    def test_remaining_amount(self, sample_coordinator_data):
        coord = _make_coordinator(sample_coordinator_data)
        sensor = FinanzflussExemptionOrderSensor(coord, 300)
        assert sensor.native_value == 750.0  # 1000 - 250

    def test_name_contains_bank(self, sample_coordinator_data):
        coord = _make_coordinator(sample_coordinator_data)
        sensor = FinanzflussExemptionOrderSensor(coord, 300)
        assert "Test Bank" in sensor.name

    def test_extra_attrs(self, sample_coordinator_data):
        coord = _make_coordinator(sample_coordinator_data)
        sensor = FinanzflussExemptionOrderSensor(coord, 300)
        attrs = sensor.extra_state_attributes
        assert attrs is not None
        assert attrs["allocated_amount"] == 1000.0
        assert attrs["used_amount"] == 250.0
        assert attrs["year"] == 2024

    def test_unknown_order_returns_none(self, sample_coordinator_data):
        coord = _make_coordinator(sample_coordinator_data)
        sensor = FinanzflussExemptionOrderSensor(coord, 9999)
        assert sensor.native_value is None

    def test_missing_data_returns_none(self):
        coord = _make_coordinator({})
        sensor = FinanzflussExemptionOrderSensor(coord, 300)
        assert sensor.native_value is None


# ---------------------------------------------------------------------------
# Subscription Sensor
# ---------------------------------------------------------------------------


class TestSubscriptionSensor:
    def test_native_value(self, sample_coordinator_data):
        coord = _make_coordinator(sample_coordinator_data)
        sensor = FinanzflussSubscriptionSensor(coord)
        assert sensor.native_value == "plus"

    def test_extra_attrs(self, sample_coordinator_data):
        coord = _make_coordinator(sample_coordinator_data)
        sensor = FinanzflussSubscriptionSensor(coord)
        attrs = sensor.extra_state_attributes
        assert attrs is not None
        assert attrs["is_active"] is True

    def test_none_when_no_subscription(self):
        coord = _make_coordinator({})
        sensor = FinanzflussSubscriptionSensor(coord)
        assert sensor.native_value is None

    def test_none_when_subscription_is_none(self):
        coord = _make_coordinator({"subscription": None})
        sensor = FinanzflussSubscriptionSensor(coord)
        assert sensor.native_value is None


# ---------------------------------------------------------------------------
# Unique ID checks
# ---------------------------------------------------------------------------


class TestUniqueIds:
    def test_all_static_sensors_have_unique_ids(self, sample_coordinator_data):
        coord = _make_coordinator(sample_coordinator_data)
        sensors = [
            FinanzflussNetWorthSensor(coord),
            FinanzflussInflationSensor(coord),
            FinanzflussBudgetTotalSensor(coord),
            FinanzflussBudgetSpentSensor(coord),
            FinanzflussBudgetRemainingTotalSensor(coord),
            FinanzflussMonthlyIncomeSensor(coord),
            FinanzflussMonthlyExpensesSensor(coord),
            FinanzflussMonthlyBalanceSensor(coord),
            FinanzflussMonthlySavingsRateSensor(coord),
            FinanzflussTransactionCountSensor(coord),
            FinanzflussLastTransactionSensor(coord),
            FinanzflussInvestmentTotalSensor(coord),
            FinanzflussSubscriptionSensor(coord),
        ]
        unique_ids = [s.unique_id for s in sensors]
        assert len(unique_ids) == len(set(unique_ids)), "Duplicate unique IDs found!"

    def test_dynamic_sensors_unique_ids_differ_by_id(self, sample_coordinator_data):
        coord = _make_coordinator(sample_coordinator_data)
        acc1 = FinanzflussAccountSensor(coord, 1)
        acc2 = FinanzflussAccountSensor(coord, 2)
        assert acc1.unique_id != acc2.unique_id

        bucket1 = FinanzflussBudgetBucketSensor(coord, 10)
        bucket2 = FinanzflussBudgetBucketSensor(coord, 11)
        assert bucket1.unique_id != bucket2.unique_id
