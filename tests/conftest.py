"""Shared test fixtures for the Finanzfluss integration."""

from __future__ import annotations

import asyncio
import sys
from unittest.mock import AsyncMock

# Windows: mock fcntl and resource to prevent Home Assistant runner module errors
if sys.platform == "win32":
    import types

    sys.modules["fcntl"] = types.ModuleType("fcntl")
    sys.modules["resource"] = types.ModuleType("resource")
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.finanzfluss.const import (
    CONF_EMAIL,
    CONF_FF_ACCESS_TOKEN,
    CONF_REFRESH_TOKEN,
    CONF_WAPI_ACCESS_TOKEN,
    DOMAIN,
)


# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
async def enable_custom_integrations(hass):
    """Enable custom integrations to be loaded in tests."""
    hass.data.pop("custom_components", None)


@pytest.fixture
def sample_coordinator_data() -> dict:
    """Return a realistic sample of coordinator data covering all endpoints."""
    return {
        "accounts": [
            {
                "id": 1,
                "name": "Girokonto",
                "balance": 1500.0,
                "currency": "EUR",
                "type": "CHECKING",
                "bankName": "Test Bank",
                "iban": "DE12345678901234567890",
                "isHidden": False,
                "lastSyncDate": "2024-01-15",
                "bankConnectionType": "API",
            },
            {
                "id": 2,
                "name": "Sparkonto",
                "balance": 5000.0,
                "currency": "EUR",
                "type": "SAVINGS",
                "bankName": "Test Bank",
                "iban": "DE98765432109876543210",
                "isHidden": False,
                "lastSyncDate": "2024-01-15",
                "bankConnectionType": "API",
            },
        ],
        "budgets": {
            "totals": {"amount": 2000.0, "spent": 1200.0},
            "buckets": [
                {
                    "id": 10,
                    "title": "Groceries",
                    "amount": 500.0,
                    "spent": 300.0,
                    "categorySlug": "groceries",
                    "color": "#FF5733",
                },
                {
                    "id": 11,
                    "title": "Transport",
                    "amount": 200.0,
                    "spent": 150.0,
                    "categorySlug": "transport",
                    "color": "#33FF57",
                },
            ],
        },
        "inflation": [
            {"date": "2023-12-01", "inflationRate": 2.8, "consumerPriceIndex": 117.2},
            {"date": "2024-01-01", "inflationRate": 2.9, "consumerPriceIndex": 118.1},
        ],
        "cashflow": {
            "income": 3500.0,
            "expenses": 2100.0,
            "savingsRate": 40.0,
            "balance": 1400.0,
        },
        "transactions": {
            "totalCount": 42,
            "transactions": [
                {
                    "id": 100,
                    "amount": -45.50,
                    "date": "2024-01-14",
                    "description": "Supermarkt",
                    "categorySlug": "groceries",
                    "accountId": 1,
                },
                {
                    "id": 101,
                    "amount": 3500.0,
                    "date": "2024-01-01",
                    "description": "Gehalt",
                    "categorySlug": "income",
                    "accountId": 1,
                },
            ],
        },
        "investments": {
            "totalValue": 25000.0,
            "positions": [
                {
                    "id": 200,
                    "name": "MSCI World ETF",
                    "isin": "IE00B4L5Y983",
                    "quantity": 10.5,
                    "marketValue": 15000.0,
                    "purchaseValue": 12000.0,
                    "gain": 3000.0,
                    "gainPercent": 25.0,
                },
                {
                    "id": 201,
                    "name": "S&P 500 ETF",
                    "isin": "IE00B5BMR087",
                    "quantity": 5.0,
                    "marketValue": 10000.0,
                    "purchaseValue": 9000.0,
                    "gain": 1000.0,
                    "gainPercent": 11.1,
                },
            ],
        },
        "exemption_orders": [
            {
                "id": 300,
                "bank": "Test Bank",
                "allocatedAmount": 1000.0,
                "usedAmount": 250.0,
                "year": 2024,
            }
        ],
        "subscription": {"tier": "plus", "isActive": True},
        "categories": [
            {"slug": "groceries", "name": "Lebensmittel"},
            {"slug": "transport", "name": "Transport"},
        ],
    }


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock ConfigEntry for the finanzfluss integration."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_EMAIL: "test@example.com",
            CONF_FF_ACCESS_TOKEN: "ff_access_token_test",
            CONF_WAPI_ACCESS_TOKEN: "wapi_access_token_test",
            CONF_REFRESH_TOKEN: "refresh_token_test",
        },
        unique_id="test@example.com",
        entry_id="test_entry_id_123",
    )


@pytest.fixture
def mock_api() -> AsyncMock:
    """Return a fully mocked FinanzflussAPI instance."""
    api = AsyncMock()
    api.login.return_value = {
        "ffAccessToken": "ff_token_mock",
        "wapiAccessToken": "wapi_token_mock",
        "refreshToken": "refresh_token_mock",
    }
    api.refresh_tokens.return_value = {
        "ffAccessToken": "ff_token_refreshed",
        "wapiAccessToken": "wapi_token_refreshed",
        "refreshToken": "refresh_token_refreshed",
    }
    api.get_accounts.return_value = {
        "accounts": [
            {
                "id": 1,
                "name": "Girokonto",
                "balance": 1500.0,
                "currency": "EUR",
                "type": "CHECKING",
                "bankName": "Test Bank",
                "iban": "DE1234",
                "isHidden": False,
                "lastSyncDate": "2024-01-15",
                "bankConnectionType": "API",
            },
        ]
    }
    api.get_budgets.return_value = {
        "totals": {"amount": 2000.0, "spent": 1200.0},
        "buckets": [
            {
                "id": 10,
                "title": "Groceries",
                "amount": 500.0,
                "spent": 300.0,
                "categorySlug": "groceries",
                "color": "#FF5733",
            },
        ],
    }
    api.get_inflation.return_value = {
        "rows": [
            {"date": "2024-01-01", "inflationRate": 2.9, "consumerPriceIndex": 118.1}
        ]
    }
    api.get_cashflow_summary.return_value = {
        "income": 3500.0,
        "expenses": 2100.0,
        "savingsRate": 40.0,
        "balance": 1400.0,
    }
    api.get_transactions.return_value = {
        "totalCount": 42,
        "transactions": [
            {
                "id": 100,
                "amount": -45.50,
                "date": "2024-01-14",
                "description": "Supermarkt",
                "categorySlug": "groceries",
                "accountId": 1,
            },
        ],
    }
    api.get_investments.return_value = {
        "totalValue": 25000.0,
        "positions": [
            {
                "id": 200,
                "name": "MSCI World ETF",
                "isin": "IE00B4L5Y983",
                "quantity": 10.5,
                "marketValue": 15000.0,
                "purchaseValue": 12000.0,
                "gain": 3000.0,
                "gainPercent": 25.0,
            },
        ],
    }
    api.get_exemption_orders.return_value = [
        {
            "id": 300,
            "bank": "Test Bank",
            "allocatedAmount": 1000.0,
            "usedAmount": 250.0,
            "year": 2024,
        }
    ]
    api.get_subscription.return_value = {"tier": "plus", "isActive": True}
    api.get_categories.return_value = [
        {"slug": "groceries", "name": "Lebensmittel"},
    ]
    return api
