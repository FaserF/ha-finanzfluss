"""API client for Finanzfluss."""

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
    ) -> dict:
        """Login to Finanzfluss."""
        from .const import API_LOGIN

        payload = {"email": email, "password": password}
        if otp_code:
            payload["otpCode"] = otp_code

        try:
            async with self.session.post(API_LOGIN, json=payload) as resp:
                if resp.status == 201:
                    return await resp.json()

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
                return await resp.json()
        except aiohttp.ClientError as err:
            raise CannotConnectError("Failed to connect to API") from err

    async def refresh_tokens(self, refresh_token: str) -> dict:
        """Refresh auth tokens."""
        from .const import API_REFRESH

        try:
            async with self.session.post(
                f"{API_REFRESH}?refresh_token={refresh_token}"
            ) as resp:
                if resp.status == 201:
                    return await resp.json()
                raise InvalidAuthError("Failed to refresh token")
        except aiohttp.ClientError as err:
            raise CannotConnectError("Failed to connect to API") from err

    async def get_accounts(self, ff_token: str, wapi_token: str) -> dict:
        """Get accounts."""
        from .const import API_ACCOUNTS

        try:
            headers = self._auth_headers(ff_token, wapi_token)
            async with self.session.get(API_ACCOUNTS, headers=headers) as resp:
                if resp.status in (401, 403):
                    raise InvalidAuthError("Authentication expired")
                resp.raise_for_status()
                return await resp.json()
        except aiohttp.ClientError as err:
            raise CannotConnectError("Failed to fetch accounts") from err

    async def get_budgets(self, ff_token: str, month_str: str) -> dict:
        """Get budgets."""
        from .const import API_BUDGETS

        try:
            headers = self._auth_headers(ff_token)
            async with self.session.get(
                f"{API_BUDGETS}?month={month_str}", headers=headers
            ) as resp:
                if resp.status in (401, 403):
                    raise InvalidAuthError("Authentication expired")
                resp.raise_for_status()
                return await resp.json()
        except aiohttp.ClientError as err:
            raise CannotConnectError("Failed to fetch budgets") from err

    async def get_inflation(
        self, ff_token: str, start_date: str, end_date: str
    ) -> dict:
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
                resp.raise_for_status()
                return await resp.json()
        except aiohttp.ClientError as err:
            raise CannotConnectError("Failed to fetch inflation") from err

    async def get_cashflow_summary(self, ff_token: str, month_str: str) -> dict:
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
                resp.raise_for_status()
                return await resp.json()
        except aiohttp.ClientError as err:
            raise CannotConnectError("Failed to fetch cashflow summary") from err

    async def get_transactions(
        self, ff_token: str, page: int = 0, size: int = 50
    ) -> dict:
        """Get transactions."""
        from .const import API_TRANSACTIONS

        try:
            headers = self._auth_headers(ff_token)
            async with self.session.get(
                f"{API_TRANSACTIONS}?page={page}&size={size}", headers=headers
            ) as resp:
                if resp.status in (401, 403):
                    raise InvalidAuthError("Authentication expired")
                resp.raise_for_status()
                return await resp.json()
        except aiohttp.ClientError as err:
            raise CannotConnectError("Failed to fetch transactions") from err

    async def get_investments(self, ff_token: str, wapi_token: str) -> dict:
        """Get investments."""
        from .const import API_INVESTMENTS

        try:
            headers = self._auth_headers(ff_token, wapi_token)
            async with self.session.get(API_INVESTMENTS, headers=headers) as resp:
                if resp.status in (401, 403):
                    raise InvalidAuthError("Authentication expired")
                resp.raise_for_status()
                return await resp.json()
        except aiohttp.ClientError as err:
            raise CannotConnectError("Failed to fetch investments") from err

    async def get_exemption_orders(self, ff_token: str) -> list:
        """Get exemption orders."""
        from .const import API_EXEMPTION_ORDERS

        try:
            headers = self._auth_headers(ff_token)
            async with self.session.get(API_EXEMPTION_ORDERS, headers=headers) as resp:
                if resp.status in (401, 403):
                    raise InvalidAuthError("Authentication expired")
                resp.raise_for_status()
                return await resp.json()
        except aiohttp.ClientError as err:
            raise CannotConnectError("Failed to fetch exemption orders") from err

    async def get_subscription(self, ff_token: str) -> dict:
        """Get subscription details."""
        from .const import API_SUBSCRIPTION

        try:
            headers = self._auth_headers(ff_token)
            async with self.session.get(API_SUBSCRIPTION, headers=headers) as resp:
                if resp.status in (401, 403):
                    raise InvalidAuthError("Authentication expired")
                resp.raise_for_status()
                return await resp.json()
        except aiohttp.ClientError as err:
            raise CannotConnectError("Failed to fetch subscription") from err

    async def get_categories(self, ff_token: str) -> list:
        """Get categories."""
        from .const import API_CATEGORIES

        try:
            headers = self._auth_headers(ff_token)
            async with self.session.get(API_CATEGORIES, headers=headers) as resp:
                if resp.status in (401, 403):
                    raise InvalidAuthError("Authentication expired")
                resp.raise_for_status()
                return await resp.json()
        except aiohttp.ClientError as err:
            raise CannotConnectError("Failed to fetch categories") from err
