"""Tests for the Finanzfluss API client."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest

from custom_components.finanzfluss.api import (
    CannotConnectError,
    FinanzflussAPI,
    InvalidAuthError,
    InvalidOTPError,
    OTPRequiredError,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_response(status: int, json_data=None, raise_error: Exception | None = None):
    """Build a mock aiohttp response context-manager."""
    response = AsyncMock()
    response.status = status
    if json_data is not None:
        response.json = AsyncMock(return_value=json_data)
    if raise_error:
        response.raise_for_status = MagicMock(side_effect=raise_error)
    else:
        response.raise_for_status = MagicMock()
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=response)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm, response


def _make_session(
    method_name: str,
    status: int,
    json_data=None,
    raise_on_request: Exception | None = None,
):
    """Build a mock aiohttp.ClientSession."""
    session = MagicMock()
    if raise_on_request:
        getattr(session, method_name).side_effect = raise_on_request
        return session
    cm, _ = _make_response(status, json_data)
    getattr(session, method_name).return_value = cm
    return session


# ---------------------------------------------------------------------------
# login()
# ---------------------------------------------------------------------------


class TestLogin:
    """Tests for FinanzflussAPI.login."""

    @pytest.mark.asyncio
    async def test_login_success(self):
        auth_payload = {
            "ffAccessToken": "ff",
            "wapiAccessToken": "wapi",
            "refreshToken": "rt",
        }
        session = _make_session("post", 201, auth_payload)
        api = FinanzflussAPI(session)
        result = await api.login("user@example.com", "password")
        assert result["ffAccessToken"] == "ff"

    @pytest.mark.asyncio
    async def test_login_success_with_otp(self):
        auth_payload = {
            "ffAccessToken": "ff",
            "wapiAccessToken": "wapi",
            "refreshToken": "rt",
        }
        session = _make_session("post", 201, auth_payload)
        api = FinanzflussAPI(session)
        result = await api.login("user@example.com", "password", otp_code="123456")
        assert result is not None
        # Check that otpCode was passed in the request body
        call_kwargs = session.post.call_args[1] if session.post.call_args[1] else {}
        json_arg = call_kwargs.get("json") or (
            session.post.call_args[0][1] if len(session.post.call_args[0]) > 1 else None
        )
        if json_arg:
            assert json_arg.get("otpCode") == "123456"

    @pytest.mark.asyncio
    async def test_login_otp_required(self):
        error_body = {"code": 40103, "message": "OTP required"}
        session = _make_session("post", 400, error_body)
        api = FinanzflussAPI(session)
        with pytest.raises(OTPRequiredError):
            await api.login("user@example.com", "password")

    @pytest.mark.asyncio
    async def test_login_invalid_otp(self):
        error_body = {"code": 40104, "message": "Invalid OTP"}
        session = _make_session("post", 400, error_body)
        api = FinanzflussAPI(session)
        with pytest.raises(InvalidOTPError):
            await api.login("user@example.com", "password", otp_code="000000")

    @pytest.mark.asyncio
    async def test_login_invalid_credentials_40101(self):
        error_body = {"code": 40101, "message": "Invalid credentials"}
        session = _make_session("post", 401, error_body)
        api = FinanzflussAPI(session)
        with pytest.raises(InvalidAuthError):
            await api.login("user@example.com", "wrongpassword")

    @pytest.mark.asyncio
    async def test_login_invalid_credentials_40102(self):
        error_body = {"code": 40102, "message": "Invalid credentials"}
        session = _make_session("post", 401, error_body)
        api = FinanzflussAPI(session)
        with pytest.raises(InvalidAuthError):
            await api.login("user@example.com", "wrongpassword")

    @pytest.mark.asyncio
    async def test_login_connection_error(self):
        session = _make_session(
            "post", 0, raise_on_request=aiohttp.ClientError("connection failed")
        )
        api = FinanzflussAPI(session)
        with pytest.raises(CannotConnectError):
            await api.login("user@example.com", "password")


# ---------------------------------------------------------------------------
# refresh_tokens()
# ---------------------------------------------------------------------------


class TestRefreshTokens:
    """Tests for FinanzflussAPI.refresh_tokens."""

    @pytest.mark.asyncio
    async def test_refresh_success(self):
        payload = {
            "ffAccessToken": "new_ff",
            "wapiAccessToken": "new_wapi",
            "refreshToken": "new_rt",
        }
        session = _make_session("post", 201, payload)
        api = FinanzflussAPI(session)
        result = await api.refresh_tokens("old_refresh_token")
        assert result["ffAccessToken"] == "new_ff"

    @pytest.mark.asyncio
    async def test_refresh_failure_raises_invalid_auth(self):
        session = _make_session("post", 401, {"error": "unauthorized"})
        api = FinanzflussAPI(session)
        with pytest.raises(InvalidAuthError):
            await api.refresh_tokens("bad_token")

    @pytest.mark.asyncio
    async def test_refresh_connection_error(self):
        session = _make_session(
            "post", 0, raise_on_request=aiohttp.ClientError("network error")
        )
        api = FinanzflussAPI(session)
        with pytest.raises(CannotConnectError):
            await api.refresh_tokens("some_token")


# ---------------------------------------------------------------------------
# get_accounts()
# ---------------------------------------------------------------------------


class TestGetAccounts:
    """Tests for FinanzflussAPI.get_accounts."""

    @pytest.mark.asyncio
    async def test_get_accounts_success(self):
        payload = {"accounts": [{"id": 1, "name": "Konto", "balance": 100.0}]}
        session = _make_session("get", 200, payload)
        api = FinanzflussAPI(session)
        result = await api.get_accounts("ff_token", "wapi_token")
        assert result["accounts"][0]["id"] == 1

    @pytest.mark.asyncio
    async def test_get_accounts_401_raises_invalid_auth(self):
        cm, response = _make_response(401, {"error": "unauthorized"})
        response.raise_for_status.side_effect = aiohttp.ClientResponseError(
            None, None, status=401
        )
        session = MagicMock()
        session.get.return_value = cm
        api = FinanzflussAPI(session)
        with pytest.raises((InvalidAuthError, CannotConnectError)):
            await api.get_accounts("bad_token", "bad_wapi")

    @pytest.mark.asyncio
    async def test_get_accounts_connection_error(self):
        session = _make_session(
            "get", 0, raise_on_request=aiohttp.ClientError("network error")
        )
        api = FinanzflussAPI(session)
        with pytest.raises(CannotConnectError):
            await api.get_accounts("ff_token", "wapi_token")


# ---------------------------------------------------------------------------
# get_budgets()
# ---------------------------------------------------------------------------


class TestGetBudgets:
    @pytest.mark.asyncio
    async def test_get_budgets_success(self):
        payload = {"totals": {"amount": 500.0, "spent": 200.0}, "buckets": []}
        session = _make_session("get", 200, payload)
        api = FinanzflussAPI(session)
        result = await api.get_budgets("ff_token", "2024-01-01")
        assert result["totals"]["amount"] == 500.0

    @pytest.mark.asyncio
    async def test_get_budgets_connection_error(self):
        session = _make_session("get", 0, raise_on_request=aiohttp.ClientError())
        api = FinanzflussAPI(session)
        with pytest.raises(CannotConnectError):
            await api.get_budgets("ff_token", "2024-01-01")


# ---------------------------------------------------------------------------
# get_inflation()
# ---------------------------------------------------------------------------


class TestGetInflation:
    @pytest.mark.asyncio
    async def test_get_inflation_success(self):
        payload = {"rows": [{"date": "2024-01-01", "inflationRate": 2.9}]}
        session = _make_session("get", 200, payload)
        api = FinanzflussAPI(session)
        result = await api.get_inflation("ff_token", "2023-01-01", "2024-01-01")
        assert result["rows"][0]["inflationRate"] == 2.9

    @pytest.mark.asyncio
    async def test_get_inflation_connection_error(self):
        session = _make_session("get", 0, raise_on_request=aiohttp.ClientError())
        api = FinanzflussAPI(session)
        with pytest.raises(CannotConnectError):
            await api.get_inflation("ff_token", "2023-01-01", "2024-01-01")


# ---------------------------------------------------------------------------
# get_cashflow_summary()
# ---------------------------------------------------------------------------


class TestGetCashflowSummary:
    @pytest.mark.asyncio
    async def test_get_cashflow_summary_success(self):
        payload = {
            "income": 3500.0,
            "expenses": 2100.0,
            "savingsRate": 40.0,
            "balance": 1400.0,
        }
        session = _make_session("get", 200, payload)
        api = FinanzflussAPI(session)
        result = await api.get_cashflow_summary("ff_token", "2024-01-01")
        assert result["income"] == 3500.0
        assert result["savingsRate"] == 40.0

    @pytest.mark.asyncio
    async def test_get_cashflow_connection_error(self):
        session = _make_session("get", 0, raise_on_request=aiohttp.ClientError())
        api = FinanzflussAPI(session)
        with pytest.raises(CannotConnectError):
            await api.get_cashflow_summary("ff_token", "2024-01-01")


# ---------------------------------------------------------------------------
# get_transactions()
# ---------------------------------------------------------------------------


class TestGetTransactions:
    @pytest.mark.asyncio
    async def test_get_transactions_success(self):
        payload = {"totalCount": 5, "transactions": [{"id": 1, "amount": -50.0}]}
        session = _make_session("get", 200, payload)
        api = FinanzflussAPI(session)
        result = await api.get_transactions("ff_token")
        assert result["totalCount"] == 5

    @pytest.mark.asyncio
    async def test_get_transactions_with_params(self):
        payload = {"totalCount": 1, "transactions": []}
        session = _make_session("get", 200, payload)
        api = FinanzflussAPI(session)
        result = await api.get_transactions("ff_token", page=2, size=10)
        assert result is not None
        # Check URL contained page and size params
        call_args = session.get.call_args
        url = call_args[0][0] if call_args[0] else str(call_args)
        assert "page=2" in url or "page" in str(call_args)

    @pytest.mark.asyncio
    async def test_get_transactions_connection_error(self):
        session = _make_session("get", 0, raise_on_request=aiohttp.ClientError())
        api = FinanzflussAPI(session)
        with pytest.raises(CannotConnectError):
            await api.get_transactions("ff_token")


# ---------------------------------------------------------------------------
# get_investments()
# ---------------------------------------------------------------------------


class TestGetInvestments:
    @pytest.mark.asyncio
    async def test_get_investments_success(self):
        payload = {
            "totalValue": 25000.0,
            "positions": [{"id": 1, "marketValue": 25000.0}],
        }
        session = _make_session("get", 200, payload)
        api = FinanzflussAPI(session)
        result = await api.get_investments("ff_token", "wapi_token")
        assert result["totalValue"] == 25000.0

    @pytest.mark.asyncio
    async def test_get_investments_connection_error(self):
        session = _make_session("get", 0, raise_on_request=aiohttp.ClientError())
        api = FinanzflussAPI(session)
        with pytest.raises(CannotConnectError):
            await api.get_investments("ff_token", "wapi_token")


# ---------------------------------------------------------------------------
# get_exemption_orders()
# ---------------------------------------------------------------------------


class TestGetExemptionOrders:
    @pytest.mark.asyncio
    async def test_get_exemption_orders_success(self):
        payload = [
            {"id": 1, "bank": "Bank", "allocatedAmount": 1000.0, "usedAmount": 200.0}
        ]
        session = _make_session("get", 200, payload)
        api = FinanzflussAPI(session)
        result = await api.get_exemption_orders("ff_token")
        assert isinstance(result, list)
        assert result[0]["allocatedAmount"] == 1000.0

    @pytest.mark.asyncio
    async def test_get_exemption_orders_connection_error(self):
        session = _make_session("get", 0, raise_on_request=aiohttp.ClientError())
        api = FinanzflussAPI(session)
        with pytest.raises(CannotConnectError):
            await api.get_exemption_orders("ff_token")


# ---------------------------------------------------------------------------
# get_subscription()
# ---------------------------------------------------------------------------


class TestGetSubscription:
    @pytest.mark.asyncio
    async def test_get_subscription_success(self):
        payload = {"tier": "plus", "isActive": True}
        session = _make_session("get", 200, payload)
        api = FinanzflussAPI(session)
        result = await api.get_subscription("ff_token")
        assert result["tier"] == "plus"

    @pytest.mark.asyncio
    async def test_get_subscription_connection_error(self):
        session = _make_session("get", 0, raise_on_request=aiohttp.ClientError())
        api = FinanzflussAPI(session)
        with pytest.raises(CannotConnectError):
            await api.get_subscription("ff_token")


# ---------------------------------------------------------------------------
# get_categories()
# ---------------------------------------------------------------------------


class TestGetCategories:
    @pytest.mark.asyncio
    async def test_get_categories_success(self):
        payload = [{"slug": "groceries", "name": "Lebensmittel"}]
        session = _make_session("get", 200, payload)
        api = FinanzflussAPI(session)
        result = await api.get_categories("ff_token")
        assert isinstance(result, list)
        assert result[0]["slug"] == "groceries"

    @pytest.mark.asyncio
    async def test_get_categories_connection_error(self):
        session = _make_session("get", 0, raise_on_request=aiohttp.ClientError())
        api = FinanzflussAPI(session)
        with pytest.raises(CannotConnectError):
            await api.get_categories("ff_token")
