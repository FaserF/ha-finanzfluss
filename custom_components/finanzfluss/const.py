"""Constants for the Finanzfluss integration."""

import logging

DOMAIN = "finanzfluss"
LOGGER = logging.getLogger(__package__)

# API URLs
BASE_URL = "https://hippoverse.finanzfluss.de/api"
API_LOGIN = f"{BASE_URL}/v3/auth/login"
API_REFRESH = f"{BASE_URL}/v2/auth/refreshAuth"
API_ACCOUNTS = f"{BASE_URL}/v3/accounts"
API_INFLATION = f"{BASE_URL}/v1/inflation"
API_BUDGETS = f"{BASE_URL}/v5/budgetBuckets/monthlyOverview"
API_CASHFLOW = f"{BASE_URL}/v1/cashFlowAnalytics/summary"
API_CASHFLOW_HISTORY = f"{BASE_URL}/v3/cashFlowAnalytics/history"
API_TRANSACTIONS = f"{BASE_URL}/v3/transactions"
API_INVESTMENTS = f"{BASE_URL}/v2/investments/breakdown"
API_EXEMPTION_ORDERS = f"{BASE_URL}/v1/exemptionOrders"
API_SUBSCRIPTION = f"{BASE_URL}/v2/subscription"
API_CATEGORIES = f"{BASE_URL}/v2/categories"

# Configuration Keys
CONF_EMAIL = "email"
CONF_PASSWORD = "password"
CONF_FF_ACCESS_TOKEN = "ff_access_token"
CONF_WAPI_ACCESS_TOKEN = "wapi_access_token"
CONF_REFRESH_TOKEN = "refresh_token"
CONF_USER_UUID = "user_uuid"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_FALLBACK_CALCULATION = "fallback_calculation"

DEFAULT_SCAN_INTERVAL = 86400  # seconds (24 hours)
MIN_SCAN_INTERVAL = 600  # seconds (10 minutes)

