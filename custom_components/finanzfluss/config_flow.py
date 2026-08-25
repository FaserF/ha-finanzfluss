"""Config flow for Finanzfluss integration."""

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    CannotConnectError,
    FinanzflussAPI,
    FinanzflussAPIError,
    InvalidAuthError,
    InvalidOTPError,
    OTPRequiredError,
)
from .const import (
    CONF_EMAIL,
    CONF_FALLBACK_CALCULATION,
    CONF_FF_ACCESS_TOKEN,
    CONF_PASSWORD,
    CONF_REFRESH_TOKEN,
    CONF_SCAN_INTERVAL,
    CONF_USER_UUID,
    CONF_WAPI_ACCESS_TOKEN,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MIN_SCAN_INTERVAL,
)


class FinanzflussConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Finanzfluss."""

    VERSION = 1

    @staticmethod
    @config_entries.callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> FinanzflussOptionsFlow:
        """Return the options flow handler."""
        return FinanzflussOptionsFlow(config_entry)

    def __init__(self) -> None:
        """Initialize flow."""
        self._email: str | None = None
        self._password: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            email: str = user_input[CONF_EMAIL]
            password: str = user_input[CONF_PASSWORD]

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
    ) -> ConfigFlowResult:
        """Handle MFA step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            otp_code = user_input["otp_code"]
            session = async_get_clientsession(self.hass)
            api = FinanzflussAPI(session)
            email = self._email or ""
            password = self._password or ""

            try:
                auth_data = await api.login(email, password, otp_code)
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
            step_id="mfa",
            data_schema=vol.Schema(
                {
                    vol.Required("otp_code"): str,
                }
            ),
            errors=errors,
        )


class FinanzflussOptionsFlow(config_entries.OptionsFlow):
    """Handle options for the Finanzfluss integration."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry
        self._new_email: str | None = None
        self._new_password: str | None = None
        self._pending_interval: int = DEFAULT_SCAN_INTERVAL

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage integration options (update interval + optional re-auth)."""
        errors: dict[str, str] = {}

        current_interval_minutes = (
            self._config_entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            // 60
        )
        current_fallback = self._config_entry.options.get(
            CONF_FALLBACK_CALCULATION, True
        )

        if user_input is not None:
            interval_minutes = user_input.get(
                CONF_SCAN_INTERVAL, current_interval_minutes
            )
            scan_interval_seconds = max(MIN_SCAN_INTERVAL, interval_minutes * 60)
            fallback_enabled = user_input.get(
                CONF_FALLBACK_CALCULATION, current_fallback
            )

            new_email = user_input.get(CONF_EMAIL, "").strip()
            new_password = user_input.get(CONF_PASSWORD, "").strip()

            # If credentials were provided, re-authenticate before saving
            if new_email and new_password:
                self._new_email = new_email
                self._new_password = new_password
                self._pending_interval = scan_interval_seconds
                self._pending_fallback = fallback_enabled
                return await self.async_step_reauth_mfa(None)

            return self.async_create_entry(
                title="",
                data={
                    CONF_SCAN_INTERVAL: scan_interval_seconds,
                    CONF_FALLBACK_CALCULATION: fallback_enabled,
                },
            )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SCAN_INTERVAL,
                        default=current_interval_minutes,
                    ): vol.All(int, vol.Range(min=MIN_SCAN_INTERVAL // 60)),
                    vol.Required(
                        CONF_FALLBACK_CALCULATION,
                        default=current_fallback,
                    ): bool,
                    vol.Optional(CONF_EMAIL, default=""): str,
                    vol.Optional(CONF_PASSWORD, default=""): str,
                }
            ),
            errors=errors,
        )

    async def async_step_reauth_mfa(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle MFA during credential update in options flow."""
        errors: dict[str, str] = {}

        session = async_get_clientsession(self.hass)
        api = FinanzflussAPI(session)
        new_email = self._new_email or ""
        new_password = self._new_password or ""

        if user_input is None:
            # Attempt login without MFA first
            try:
                auth_data = await api.login(new_email, new_password)
            except OTPRequiredError:
                # MFA needed – show the OTP form
                return self.async_show_form(
                    step_id="reauth_mfa",
                    data_schema=vol.Schema({vol.Required("otp_code"): str}),
                    errors=errors,
                )
            except InvalidAuthError:
                errors["base"] = "invalid_auth"
                return self.async_show_form(
                    step_id="init",
                    data_schema=self._init_schema(),
                    errors=errors,
                )
            except CannotConnectError:
                errors["base"] = "cannot_connect"
                return self.async_show_form(
                    step_id="init",
                    data_schema=self._init_schema(),
                    errors=errors,
                )
            except FinanzflussAPIError:
                errors["base"] = "unknown"
                return self.async_show_form(
                    step_id="init",
                    data_schema=self._init_schema(),
                    errors=errors,
                )
        else:
            otp_code = user_input["otp_code"]
            try:
                auth_data = await api.login(new_email, new_password, otp_code)
            except InvalidOTPError:
                errors["base"] = "invalid_otp"
                return self.async_show_form(
                    step_id="reauth_mfa",
                    data_schema=vol.Schema({vol.Required("otp_code"): str}),
                    errors=errors,
                )
            except InvalidAuthError:
                errors["base"] = "invalid_auth"
                return self.async_show_form(
                    step_id="reauth_mfa",
                    data_schema=vol.Schema({vol.Required("otp_code"): str}),
                    errors=errors,
                )
            except CannotConnectError, FinanzflussAPIError:
                errors["base"] = "cannot_connect"
                return self.async_show_form(
                    step_id="reauth_mfa",
                    data_schema=vol.Schema({vol.Required("otp_code"): str}),
                    errors=errors,
                )

        # Persist updated credentials into config entry data
        new_data = {
            **self._config_entry.data,
            CONF_EMAIL: new_email,
            CONF_PASSWORD: new_password,
            CONF_FF_ACCESS_TOKEN: auth_data["ffAccessToken"],
            CONF_WAPI_ACCESS_TOKEN: auth_data["wapiAccessToken"],
            CONF_REFRESH_TOKEN: auth_data["refreshToken"],
            CONF_USER_UUID: auth_data["uuid"],
        }
        self.hass.config_entries.async_update_entry(
            self._config_entry, data=new_data, title=new_email
        )

        return self.async_create_entry(
            title="",
            data={
                CONF_SCAN_INTERVAL: self._pending_interval,
                CONF_FALLBACK_CALCULATION: getattr(self, "_pending_fallback", True),
            },
        )

    def _init_schema(self) -> vol.Schema:
        """Return the init step schema (used when re-showing after error)."""
        current_interval_minutes = (
            self._config_entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            // 60
        )
        current_fallback = self._config_entry.options.get(
            CONF_FALLBACK_CALCULATION, True
        )
        return vol.Schema(
            {
                vol.Required(
                    CONF_SCAN_INTERVAL,
                    default=current_interval_minutes,
                ): vol.All(int, vol.Range(min=MIN_SCAN_INTERVAL // 60)),
                vol.Required(
                    CONF_FALLBACK_CALCULATION,
                    default=current_fallback,
                ): bool,
                vol.Optional(CONF_EMAIL, default=""): str,
                vol.Optional(CONF_PASSWORD, default=""): str,
            }
        )
