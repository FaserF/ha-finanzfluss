"""API client for Finanzfluss."""

import re
from typing import Any, cast
import aiohttp


class FinanzflussAPIError(Exception):
    """Base class for API errors."""


class CannotConnectError(FinanzflussAPIError):
    """Raised when cannot connect to the API."""


class InvalidAuthError(FinanzflussAPIError):
    """Raised when authentication is invalid."""


class OTPRequiredError(FinanzflussAPIError):
    """Raised when OTP is required."""


class InvalidOTPError(FinanzflussAPIError):
    """Raised when OTP is invalid."""


def _sanitize_error(err: Exception) -> str:
    """Sanitize sensitive tokens from error messages."""
    msg = str(err)
    msg = re.sub(r"wapiAccessToken=[^&\s'\"]+", "wapiAccessToken=REDACTED", msg)
    msg = re.sub(r"Bearer\s+[A-Za-z0-9._\-]+", "Bearer REDACTED", msg)
    return msg


class FinanzflussAPI:
    """API client for Finanzfluss."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        """Initialize the API client."""
        self.session = session

    def _auth_headers(
        self, ff_token: str, wapi_token: str | None = None
    ) -> dict[str, str]:
        """Generate authentication headers."""
        headers = {
            "Authorization": f"Bearer {ff_token}",
            "Accept": "application/json",
        }
        if wapi_token:
            headers["WAPI-Authorization"] = f"Bearer {wapi_token}"
        return headers

    async def login(
        self, email: str, password: str, otp_code: str | None = None
    ) -> dict[str, Any]:
        """Login to Finanzfluss."""
        from .const import API_LOGIN

        payload = {"email": email, "password": password}
        if otp_code:
            payload["otpCode"] = otp_code

        try:
            async with self.session.post(API_LOGIN, json=payload) as resp:
                if resp.status == 201:
                    return cast(dict[str, Any], await resp.json())

                # Check body for specific error codes like 40103 (OTP required) or 40104 (Invalid OTP)
                try:
                    data = await resp.json()
                except Exception:
                    data = {}

                code = data.get("code")
                if code == 40103:
                    raise OTPRequiredError("OTP is required")
                if code == 40104:
                    raise InvalidOTPError("Invalid OTP code")

                if resp.status in (401, 403):
                    raise InvalidAuthError("Invalid credentials")
                resp.raise_for_status()
                return cast(dict[str, Any], await resp.json())
        except aiohttp.ClientError as err:
            raise CannotConnectError("Failed to connect to API") from err

    async def refresh_tokens(self, refresh_token: str) -> dict[str, Any]:
        """Refresh auth tokens."""
        from .const import API_REFRESH

        try:
            async with self.session.post(
                f"{API_REFRESH}?refresh_token={refresh_token}"
            ) as resp:
                if resp.status == 201:
                    return cast(dict[str, Any], await resp.json())
                raise InvalidAuthError("Failed to refresh token")
        except aiohttp.ClientError as err:
            raise CannotConnectError("Failed to connect to API") from err

    async def get_accounts(self, ff_token: str, wapi_token: str) -> dict[str, Any]:
        """Get accounts."""
        from .const import API_ACCOUNTS

        try:
            headers = self._auth_headers(ff_token, wapi_token)
            async with self.session.get(API_ACCOUNTS, headers=headers) as resp:
                if resp.status in (401, 403):
                    raise InvalidAuthError("Authentication expired")
                resp.raise_for_status()
                return cast(dict[str, Any], await resp.json())
        except aiohttp.ClientError as err:
            raise CannotConnectError(
                f"Failed to fetch accounts: {_sanitize_error(err)}"
            ) from err

    async def get_budgets(self, ff_token: str, month_str: str) -> dict[str, Any]:
        """Get budgets."""
        from .const import API_BUDGETS

        try:
            headers = self._auth_headers(ff_token)
            async with self.session.get(
                f"{API_BUDGETS}?month={month_str}", headers=headers
            ) as resp:
                if resp.status in (401, 403):
                    raise InvalidAuthError("Authentication expired")
                if resp.status in (400, 402, 500):
                    return {}
                resp.raise_for_status()
                return cast(dict[str, Any], await resp.json())
        except aiohttp.ClientError as err:
            raise CannotConnectError(
                f"Failed to fetch budgets: {_sanitize_error(err)}"
            ) from err

    async def get_inflation(
        self, ff_token: str, start_date: str, end_date: str
    ) -> dict[str, Any]:
        """Get inflation data."""
        from .const import API_INFLATION

        try:
            headers = self._auth_headers(ff_token)
            async with self.session.get(
                f"{API_INFLATION}?startDate={start_date}&endDate={end_date}",
                headers=headers,
            ) as resp:
                if resp.status in (401, 403):
                    raise InvalidAuthError("Authentication expired")
                if resp.status in (400, 402, 500):
                    return {}
                resp.raise_for_status()
                return cast(dict[str, Any], await resp.json())
        except aiohttp.ClientError as err:
            raise CannotConnectError(
                f"Failed to fetch inflation: {_sanitize_error(err)}"
            ) from err

    async def get_cashflow_summary(
        self, ff_token: str, month_str: str
    ) -> dict[str, Any]:
        """Get cashflow summary (all periods with granularity=month)."""
        from .const import API_CASHFLOW

        try:
            headers = self._auth_headers(ff_token)
            # granularity=month returns all monthly periods; we filter to current month in coordinator
            async with self.session.get(
                f"{API_CASHFLOW}?granularity=month", headers=headers
            ) as resp:
                if resp.status in (401, 403):
                    raise InvalidAuthError("Authentication expired")
                if resp.status in (400, 402, 500):
                    return {}
                resp.raise_for_status()
                return cast(dict[str, Any], await resp.json())
        except aiohttp.ClientError as err:
            raise CannotConnectError(
                f"Failed to fetch cashflow summary: {_sanitize_error(err)}"
            ) from err

    async def get_transactions(
        self, ff_token: str, page: int = 1, size: int = 500
    ) -> dict[str, Any]:
        """Get transactions."""
        from .const import API_TRANSACTIONS

        try:
            headers = self._auth_headers(ff_token)
            url = f"{API_TRANSACTIONS}?page={page}&perPage={size}"
            async with self.session.get(url, headers=headers) as resp:
                if resp.status in (401, 403):
                    raise InvalidAuthError("Authentication expired")
                if resp.status in (400, 402, 500):
                    return {"totalCount": 0, "transactions": []}
                resp.raise_for_status()
                return cast(dict[str, Any], await resp.json())
        except aiohttp.ClientError as err:
            raise CannotConnectError(
                f"Failed to fetch transactions: {_sanitize_error(err)}"
            ) from err

    async def get_all_transactions(
        self, ff_token: str, max_pages: int = 20
    ) -> list[dict[str, Any]]:
        """Get all transactions across all pages in steps of 500 starting from page 1."""
        all_txs: list[dict[str, Any]] = []
        page = 1
        size = 500
        while page <= max_pages:
            try:
                res = await self.get_transactions(ff_token, page=page, size=size)
                txs = res.get("transactions", [])
                if not txs:
                    break
                all_txs.extend(txs)
                total_count = res.get("totalCount")
                if total_count is not None and len(all_txs) >= total_count:
                    break
                if len(txs) < size:
                    break
                page += 1
            except Exception as err:
                from .const import LOGGER

                LOGGER.warning("Error fetching transaction page %d: %s", page, err)
                break
        return all_txs

    async def get_investments(self, ff_token: str, wapi_token: str) -> dict[str, Any]:
        """Get investments."""
        from .const import API_INVESTMENTS

        try:
            headers = self._auth_headers(ff_token, wapi_token)
            async with self.session.get(API_INVESTMENTS, headers=headers) as resp:
                if resp.status in (401, 403):
                    raise InvalidAuthError("Authentication expired")
                if resp.status in (400, 402, 500):
                    # Investment breakdown requires Finanzfluss Plus subscription
                    return {}
                resp.raise_for_status()
                return cast(dict[str, Any], await resp.json())
        except aiohttp.ClientError as err:
            raise CannotConnectError(
                f"Failed to fetch investments: {_sanitize_error(err)}"
            ) from err

    async def get_exemption_orders(
        self, ff_token: str, wapi_token: str | None = None
    ) -> list[Any]:
        """Get exemption orders."""
        from .const import API_EXEMPTION_ORDERS

        try:
            headers = self._auth_headers(ff_token, wapi_token)
            async with self.session.get(API_EXEMPTION_ORDERS, headers=headers) as resp:
                if resp.status in (401, 403):
                    raise InvalidAuthError("Authentication expired")
                if resp.status in (400, 402, 500):
                    return []
                resp.raise_for_status()
                return cast(list[Any], await resp.json())
        except aiohttp.ClientError as err:
            raise CannotConnectError(
                f"Failed to fetch exemption orders: {_sanitize_error(err)}"
            ) from err

    async def get_subscription(self, ff_token: str) -> dict[str, Any]:
        """Get subscription details."""
        from .const import API_SUBSCRIPTION

        try:
            headers = self._auth_headers(ff_token)
            async with self.session.get(API_SUBSCRIPTION, headers=headers) as resp:
                if resp.status in (401, 403):
                    raise InvalidAuthError("Authentication expired")
                if resp.status in (400, 402, 500):
                    return {}
                resp.raise_for_status()
                return cast(dict[str, Any], await resp.json())
        except aiohttp.ClientError as err:
            raise CannotConnectError(
                f"Failed to fetch subscription: {_sanitize_error(err)}"
            ) from err

    async def get_categories(
        self, ff_token: str, wapi_token: str | None = None
    ) -> list[Any]:
        """Get categories."""
        from .const import API_CATEGORIES

        try:
            headers = self._auth_headers(ff_token, wapi_token)
            async with self.session.get(API_CATEGORIES, headers=headers) as resp:
                if resp.status in (401, 403):
                    raise InvalidAuthError("Authentication expired")
                if resp.status in (400, 402, 500):
                    return []
                resp.raise_for_status()
                return cast(list[Any], await resp.json())
        except aiohttp.ClientError as err:
            raise CannotConnectError(
                f"Failed to fetch categories: {_sanitize_error(err)}"
            ) from err
