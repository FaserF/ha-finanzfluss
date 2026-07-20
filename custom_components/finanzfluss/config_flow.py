"""Config flow for Finanzfluss integration."""

from typing import Any
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    DOMAIN,
    CONF_EMAIL,
    CONF_PASSWORD,
    CONF_FF_ACCESS_TOKEN,
    CONF_WAPI_ACCESS_TOKEN,
    CONF_REFRESH_TOKEN,
    CONF_USER_UUID,
)
from .api import (
    FinanzflussAPI,
    CannotConnectError,
    InvalidAuthError,
    OTPRequiredError,
    InvalidOTPError,
    FinanzflussAPIError,
)


class FinanzflussConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Finanzfluss."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize flow."""
        self._email: str | None = None
        self._password: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            email = user_input[CONF_EMAIL]
            password = user_input[CONF_PASSWORD]

            # Check if already configured
            await self.async_set_unique_id(email.lower())
            self._abort_if_unique_id_configured()

            session = async_get_clientsession(self.hass)
            api = FinanzflussAPI(session)

            try:
                auth_data = await api.login(email, password)
            except OTPRequiredError:
                # Store credentials temporarily for the MFA step
                self._email = email
                self._password = password
                return await self.async_step_mfa()
            except InvalidAuthError:
                errors["base"] = "invalid_auth"
            except CannotConnectError:
                errors["base"] = "cannot_connect"
            except FinanzflussAPIError:
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=email,
                    data={
                        CONF_EMAIL: email,
                        CONF_PASSWORD: password,
                        CONF_FF_ACCESS_TOKEN: auth_data["ffAccessToken"],
                        CONF_WAPI_ACCESS_TOKEN: auth_data["wapiAccessToken"],
                        CONF_REFRESH_TOKEN: auth_data["refreshToken"],
                        CONF_USER_UUID: auth_data["uuid"],
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_EMAIL): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )

    async def async_step_mfa(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle MFA step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            otp_code = user_input["otp_code"]
            session = async_get_clientsession(self.hass)
            api = FinanzflussAPI(session)

            try:
                auth_data = await api.login(self._email, self._password, otp_code)
            except InvalidOTPError:
                errors["base"] = "invalid_otp"
            except InvalidAuthError:
                errors["base"] = "invalid_auth"
            except CannotConnectError:
                errors["base"] = "cannot_connect"
            except FinanzflussAPIError:
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=self._email,
                    data={
                        CONF_EMAIL: self._email,
                        CONF_PASSWORD: self._password,
                        CONF_FF_ACCESS_TOKEN: auth_data["ffAccessToken"],
                        CONF_WAPI_ACCESS_TOKEN: auth_data["wapiAccessToken"],
                        CONF_REFRESH_TOKEN: auth_data["refreshToken"],
                        CONF_USER_UUID: auth_data["uuid"],
                    },
                )

        return self.async_show_form(
            step_id="mfa",
            data_schema=vol.Schema(
                {
                    vol.Required("otp_code"): str,
                }
            ),
            errors=errors,
        )
