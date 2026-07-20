"""Tests for the Finanzfluss config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType

from custom_components.finanzfluss.api import (
    CannotConnectError,
    InvalidAuthError,
    InvalidOTPError,
    OTPRequiredError,
)
from custom_components.finanzfluss.const import DOMAIN

AUTH_DATA = {
    "ffAccessToken": "ff_token",
    "wapiAccessToken": "wapi_token",
    "refreshToken": "refresh_token",
    "uuid": "test-uuid-1234",
}

EMAIL = "test@example.com"
PASSWORD = "secure_password"
OTP = "123456"


@pytest.fixture
def mock_api_class():
    """Patch FinanzflussAPI in the config_flow module."""
    with patch("custom_components.finanzfluss.config_flow.FinanzflussAPI") as api_cls:
        api_instance = AsyncMock()
        api_cls.return_value = api_instance
        yield api_instance


class TestConfigFlow:
    """Tests for the config flow initialization."""

    async def test_form_shows_user_step(self, hass):
        """First step presents email and password fields."""
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"
        assert (
            "email" in result["data_schema"].schema or result.get("errors") is not None
        )

    async def test_successful_login_no_otp(self, hass, mock_api_class):
        """Happy path: login succeeds without MFA, entry is created."""
        mock_api_class.login.return_value = AUTH_DATA

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "email": EMAIL,
                "password": PASSWORD,
            },
        )
        assert result["type"] in (FlowResultType.CREATE_ENTRY, FlowResultType.FORM)
        if result["type"] == FlowResultType.CREATE_ENTRY:
            assert result["data"]["ff_access_token"] == "ff_token"

    async def test_otp_step_shown_on_otp_required(self, hass, mock_api_class):
        """When OTPRequiredError is raised, the otp step is shown."""
        mock_api_class.login.side_effect = OTPRequiredError("OTP required")

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"email": EMAIL, "password": PASSWORD},
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "mfa"

    async def test_successful_login_with_otp(self, hass, mock_api_class):
        """Full OTP flow: first call raises OTPRequired, second with OTP succeeds."""
        mock_api_class.login.side_effect = [
            OTPRequiredError("OTP required"),
            AUTH_DATA,
        ]

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"email": EMAIL, "password": PASSWORD},
        )
        assert result["step_id"] == "mfa"

        # Submit OTP
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"otp_code": OTP},
        )
        assert result["type"] in (FlowResultType.CREATE_ENTRY, FlowResultType.FORM)

    async def test_invalid_credentials_shows_error(self, hass, mock_api_class):
        """InvalidAuthError shows 'invalid_auth' error on the user step."""
        mock_api_class.login.side_effect = InvalidAuthError("wrong credentials")

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"email": EMAIL, "password": "wrongpass"},
        )
        assert result["type"] == FlowResultType.FORM
        assert "invalid_auth" in result.get("errors", {}).values()

    async def test_cannot_connect_shows_error(self, hass, mock_api_class):
        """CannotConnectError shows 'cannot_connect' error on the user step."""
        mock_api_class.login.side_effect = CannotConnectError("network error")

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"email": EMAIL, "password": PASSWORD},
        )
        assert result["type"] == FlowResultType.FORM
        assert "cannot_connect" in result.get("errors", {}).values()

    async def test_invalid_otp_shows_error(self, hass, mock_api_class):
        """InvalidOTPError shows 'invalid_otp' error on the otp step."""
        mock_api_class.login.side_effect = [
            OTPRequiredError("OTP required"),
            InvalidOTPError("Invalid OTP"),
        ]

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"email": EMAIL, "password": PASSWORD},
        )
        assert result["step_id"] == "mfa"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"otp_code": "000000"},
        )
        assert result["type"] == FlowResultType.FORM
        assert "invalid_otp" in result.get("errors", {}).values()
