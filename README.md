# Finanzfluss Copilot (for Home Assistant)

[![GitHub Release](https://img.shields.io/github/release/fseitz/ha-finanzfluss.svg?style=flat-square)](https://github.com/fseitz/ha-finanzfluss/releases)
[![Downloads (Current release)](https://img.shields.io/github/downloads/fseitz/ha-finanzfluss/latest/finanzfluss.zip?label=Downloads%20(Current%20release)&style=flat-square)](https://github.com/fseitz/ha-finanzfluss/releases)
[![License](https://img.shields.io/github/license/fseitz/ha-finanzfluss.svg?style=flat-square)](LICENSE)
[![hacs](https://img.shields.io/badge/HACS-custom-orange.svg?style=flat-square)](https://hacs.xyz)
[![Add to Home Assistant](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=finanzfluss)
[![CI Orchestrator](https://github.com/fseitz/ha-finanzfluss/actions/workflows/ci-orchestrator.yml/badge.svg)](https://github.com/fseitz/ha-finanzfluss/actions/workflows/ci-orchestrator.yml)

A **Home Assistant custom integration** for [Finanzfluss Copilot](https://www.finanzfluss.de/), the German personal finance dashboard. It synchronises your accounts, budgets, cashflow, inflation data and investment portfolio directly into Home Assistant — enabling automations, Lovelace dashboards, and long-term history tracking.

## 🧭 Quick Links

| | | | |
| :--- | :--- | :--- | :--- |
| [✨ Features](#-features) | [📦 Installation](#-installation) | [⚙️ Configuration](#️-configuration) | [🛠️ Options Flow](#️-options-flow) |
| [📡 Entities](#-entities) | [📖 Automation Examples](#-automation-examples) | [❓ FAQ](#-troubleshooting--faq) | [🧑‍💻 Development](#-development) |

---

## ✨ Features

- 📊 **Net worth sensor** — total of all visible accounts + depot value (Plus required)
- 🏦 **Per-account sensors** — one sensor per connected bank account / depot
- 💰 **Monthly cashflow** — income, expenses, balance and savings rate for the current month
- 📅 **Budget tracking** — overall budget limits, spending, and per-category buckets
- 📈 **Inflation rate** — latest German CPI-based inflation rate with 12-month history
- 🏷️ **Exemption orders** (Freistellungsaufträge) — remaining allowance per bank
- 💼 **Investment breakdown** — positions with market value, gain, and ISIN *(Plus required)*
- 🔐 **Automatic token refresh** — tokens are refreshed transparently without re-login
- 🛡️ **Anti-ban protection** — mandatory 5–30 s jitter + exponential backoff on rate limits
- 🌐 **Full localization** — English and German translations included

---

## ❤️ Support This Project

> I maintain this integration in my **free time alongside my regular job** — bug hunting, new features, testing on real devices. Every star and donation helps me stay motivated and dedicate more time to open-source work.
>
> **This project is and will always remain 100% free.** There are no "Premium Upgrades", paid features, or subscriptions. Every feature is available to everyone.

<div align="center">

[![GitHub Sponsors](https://img.shields.io/badge/Sponsor%20on-GitHub-%23EA4AAA?style=for-the-badge&logo=github-sponsors&logoColor=white)](https://github.com/sponsors/fseitz)&nbsp;&nbsp;
[![PayPal](https://img.shields.io/badge/Donate%20via-PayPal-%2300457C?style=for-the-badge&logo=paypal&logoColor=white)](https://paypal.me/fseitz)

</div>

---

## 📦 Installation

### Via HACS (Recommended)

This integration is fully compatible with [HACS](https://hacs.xyz/).

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?repository=fseitz/ha-finanzfluss&category=integration)

> [!NOTE]
> This integration is currently a **custom repository**. Add it manually to HACS:

1. Open HACS → **Integrations** → ⋮ → **Custom repositories**
2. Add `fseitz/ha-finanzfluss` with category **Integration**
3. Search for **Finanzfluss** and install
4. Restart Home Assistant

### Manual Installation

1. Download the latest release from the [Releases page](https://github.com/fseitz/ha-finanzfluss/releases).
2. Extract the `custom_components/finanzfluss/` folder into your HA `config/custom_components/` directory.
3. Restart Home Assistant.

---

## ⚙️ Configuration

Adding the integration is entirely done via the UI. **No YAML configuration is required.**

1. Navigate to **Settings → Devices & Services** in Home Assistant.
2. Click **Add Integration** and search for **Finanzfluss**.
3. Follow the guided setup:

| Field | Description |
|---|---|
| Email | Your Finanzfluss login email |
| Password | Your Finanzfluss login password |
| OTP Code | 6-digit code from your authenticator app *(only if MFA is enabled)* |

Tokens are stored securely in the HA config entry and refreshed automatically — no password re-entry is needed after initial setup.

---

## 🛠️ Options Flow

After the initial setup, click **Configure** on the integration card to adjust behaviour without re-adding the integration.

| Option | Default | Description |
|:--- |:---:|:--- |
| **Update interval** | 1440 min (24 h) | How frequently to poll the Finanzfluss API. Minimum: 10 minutes. |
| **New email** | *(empty)* | Change the login email address. Leave empty to keep the current one. |
| **New password** | *(empty)* | Change the login password. Leave empty to keep the current one. |

> [!NOTE]
> If you fill in both email **and** password, the integration will re-authenticate immediately and update the stored tokens. If MFA is enabled on the account, you will be prompted for a fresh OTP code.

> [!TIP]
> Changing the update interval restarts the integration automatically so the new polling rate takes effect immediately.

---

## 📡 Entities

All entities belong to a single **Finanzfluss Copilot** device.

### 🌐 Summary Sensors (always available)

#### `sensor.finanzfluss_net_worth` — Net Worth / Gesamtvermögen

| | |
|---|---|
| **State** | Sum of all visible (non-hidden) account balances + depot value (Plus only) |
| **Unit** | EUR |
| **Device class** | `monetary` |

**Attributes:**

| Attribute | Description |
|---|---|
| `subscription_tier` | Plan tier (`free`, `plus`) |
| `subscription_active` | Whether the subscription is active |
| `investments_total` | Total depot market value in EUR *(Plus only)* |
| `investments_note` | Shown when investments are not accessible (no Plus) |

---

#### `sensor.finanzfluss_monthly_income` — Monatliche Einnahmen

| | |
|---|---|
| **State** | Total income for the current calendar month |
| **Unit** | EUR |

**Attributes:**

| Attribute | Description |
|---|---|
| `period` | ISO date of the current period (`YYYY-MM-01`) |
| `history` | Last 12 months of `{date, income, expenses, savings}` |
| `categories` | All transaction categories |

---

#### `sensor.finanzfluss_monthly_expenses` — Monatliche Ausgaben

| | |
|---|---|
| **State** | Total expenses for the current month (positive value) |
| **Unit** | EUR |

---

#### `sensor.finanzfluss_monthly_balance` — Monatliche Bilanz

| | |
|---|---|
| **State** | Income minus expenses for the current month |
| **Unit** | EUR |

---

#### `sensor.finanzfluss_savings_rate` — Monatliche Sparquote

| | |
|---|---|
| **State** | Savings as percentage of income |
| **Unit** | % |

---

#### `sensor.finanzfluss_budget_remaining` — Restbudget

| | |
|---|---|
| **State** | Total budget limit minus total spent this month |
| **Unit** | EUR |

---

#### `sensor.finanzfluss_investment_total` — Gesamtinvestitionen *(Plus required)*

| | |
|---|---|
| **State** | Total market value of all investment positions |
| **Unit** | EUR |

**Attributes:**

| Attribute | Description |
|---|---|
| `total_gain` | Absolute gain across all positions (EUR) |
| `total_purchase_value` | Total amount invested (EUR) |
| `total_gain_percent` | Overall portfolio return (%) |

---

### 🏦 Account Sensors (one per account)

**Entity ID pattern:** `sensor.finanzfluss_account_<name>`

| | |
|---|---|
| **State** | Current account balance |
| **Unit** | EUR (or account currency) |

**Attributes (all accounts):**

| Attribute | Description |
|---|---|
| `id` | Internal Finanzfluss account ID |
| `type` | `02_cash` = bank account, `01_depot` = securities depot |
| `bank_name` | Bank name (e.g. `ING`, `Trade Republic`) |
| `iban` | IBAN |
| `is_hidden` | Whether hidden in dashboard |
| `last_sync` | Last synchronisation timestamp |
| `bank_connection_type` | `FIN_API`, `WEALTH_API`, or `null` for manual accounts |

**Extra attributes for depot accounts (`type: 01_depot`) — Plus required:**

| Attribute | Description |
|---|---|
| `positions` | List of individual holdings |
| `total_gain` | Total unrealised gain (EUR) |
| `total_purchase_value` | Total cost basis (EUR) |
| `total_gain_percent` | Overall depot return (%) |

Each `positions` entry:

| Field | Description |
|---|---|
| `name` | Security name |
| `isin` | ISIN identifier |
| `quantity` | Units held |
| `market_value` | Current value (EUR) |
| `purchase_value` | Original cost (EUR) |
| `gain` | Unrealised gain/loss (EUR) |
| `gain_percent` | Return (%) |

> [!NOTE]
> **Depot balances:** Finanzfluss returns `balance: 0` for all depot accounts from the `/v3/accounts` endpoint. The real market value is gated behind a **Plus subscription** (`/v3/investments/breakdown`). Without Plus, depot sensors show `0.00 EUR`.

---

### 📅 Budget Sensors

#### `sensor.finanzfluss_budget_total` *(disabled by default)*
Total budget limit for the current month.

#### `sensor.finanzfluss_budget_spent` *(disabled by default)*
Total amount spent against the budget this month.

#### Per-category budget: `sensor.finanzfluss_budget_<category>`
Spent amount for a specific budget category.

**Attributes:**

| Attribute | Description |
|---|---|
| `limit` | Configured spending limit |
| `category_slug` | Internal category identifier |
| `color` | Display colour (hex) |

#### `sensor.finanzfluss_budget_<category>_remaining` *(disabled by default)*
Remaining budget for a specific category.

---

### 📈 Inflation Sensor *(disabled by default)*

#### `sensor.finanzfluss_inflation_rate`

| | |
|---|---|
| **State** | Latest German inflation rate |
| **Unit** | % |

**Attributes:**

| Attribute | Description |
|---|---|
| `date` | Date of measurement |
| `consumer_price_index` | Raw CPI value |
| `history` | All monthly data rows from the last 12 months |

---

### 🏷️ Exemption Order Sensors

**`sensor.finanzfluss_exemption_order_<bank>`** — remaining Freistellungsauftrag allowance

| | |
|---|---|
| **State** | `allocated_amount` minus `used_amount` (EUR) |

**Attributes:**

| Attribute | Description |
|---|---|
| `bank` | Bank name |
| `allocated_amount` | Total exemption allocated (EUR) |
| `used_amount` | Amount used this year (EUR) |
| `year` | Tax year |

---

### 💼 Investment Position Sensors *(Plus required)*

One sensor per individual position in any depot.

**`sensor.finanzfluss_investment_<name>`** — market value of this position

**Attributes:**

| Attribute | Description |
|---|---|
| `name` | Security name |
| `isin` | ISIN |
| `quantity` | Units held |
| `purchase_value` | Cost basis (EUR) |
| `gain` | Unrealised gain/loss (EUR) |
| `gain_percent` | Return (%) |

---

### ℹ️ Supplementary Sensors *(disabled by default)*

| Entity | State | Description |
|---|---|---|
| `sensor.finanzfluss_transaction_count` | integer | Total transaction count |
| `sensor.finanzfluss_last_transaction` | EUR | Amount of most recent transaction |
| `sensor.finanzfluss_subscription` | string | Subscription tier (`free` / `plus`) |

---

## 📖 Automation Examples

<details>
<summary><strong>💰 Alert When Savings Rate Drops Below Target</strong></summary>

```yaml
alias: "Finance: Low Savings Rate Alert"
trigger:
  - platform: numeric_state
    entity_id: sensor.finanzfluss_savings_rate
    below: 10
    for:
      hours: 2
action:
  - service: notify.notify
    data:
      title: "💰 Savings Rate Below 10%"
      message: >-
        Your current monthly savings rate is
        {{ states('sensor.finanzfluss_savings_rate') }}%.
        Time to review your expenses!
```
</details>

<details>
<summary><strong>📅 Monthly Budget Exceeded Notification</strong></summary>

```yaml
alias: "Finance: Budget Exceeded"
trigger:
  - platform: numeric_state
    entity_id: sensor.finanzfluss_budget_remaining
    below: 0
action:
  - service: notify.notify
    data:
      title: "🚨 Monthly Budget Exceeded"
      message: >-
        You have exceeded your monthly budget by
        {{ (states('sensor.finanzfluss_budget_remaining') | float * -1) | round(2) }} EUR.
```
</details>

<details>
<summary><strong>📈 Portfolio Gain Notification</strong></summary>

```yaml
alias: "Finance: Investment Portfolio Update"
trigger:
  - platform: time
    at: "09:00:00"
condition:
  - condition: time
    weekday:
      - mon
action:
  - service: notify.notify
    data:
      title: "📈 Weekly Portfolio Summary"
      message: >-
        Total investments: {{ states('sensor.finanzfluss_investment_total') }} EUR.
        Net worth: {{ states('sensor.finanzfluss_net_worth') }} EUR.
```
</details>

<details>
<summary><strong>🏷️ Freistellungsauftrag Almost Used Up</strong></summary>

```yaml
alias: "Finance: Exemption Order Warning"
trigger:
  - platform: template
    value_template: >-
      {% set remaining = states('sensor.finanzfluss_exemption_order_ing') | float %}
      {{ remaining < 100 and remaining > 0 }}
action:
  - service: notify.notify
    data:
      title: "🏷️ Freistellungsauftrag Fast Aufgebraucht"
      message: >-
        Noch {{ states('sensor.finanzfluss_exemption_order_ing') }} EUR
        Freistellungsauftrag bei ING verfügbar.
```
</details>

<details>
<summary><strong>💸 High Monthly Expenses Alert</strong></summary>

```yaml
alias: "Finance: High Expenses This Month"
trigger:
  - platform: numeric_state
    entity_id: sensor.finanzfluss_monthly_expenses
    above: 3000
action:
  - service: notify.notify
    data:
      title: "💸 Hohe Ausgaben diesen Monat"
      message: >-
        Diesen Monat wurden bereits
        {{ states('sensor.finanzfluss_monthly_expenses') }} EUR ausgegeben.
```
</details>

---

## 🔒 Privacy & Security

- All API calls go **directly** to `hippoverse.finanzfluss.de` — no third-party relay or cloud bridge
- Credentials stored **encrypted** in the HA config entry store
- Token refresh happens **automatically** — no password re-entry after initial setup
- The anti-ban mechanism (5–30 s random jitter + exponential backoff) protects your account from being rate-limited or blocked

---

## 🗂️ Diagnostics

**Settings → Devices & Services → Finanzfluss → ⋮ → Download Diagnostics**

Exports coordinator state with sensitive fields (tokens, passwords) redacted for safe sharing in bug reports.

---

## ❓ Troubleshooting & FAQ

### Depot accounts show 0.00 EUR?

The Finanzfluss API returns `balance: 0` for all depot accounts from the standard accounts endpoint. Real market values are gated behind a **Plus subscription** and fetched from the investments endpoint. The `investments_note` attribute on the Net Worth sensor confirms whether Plus is active.

### Cashflow / budget sensors show "Unknown"?

Requires at least one month of transaction data in Finanzfluss Copilot. Check the Home Assistant logs for `WARNING` messages from the `finanzfluss` component.

### Net worth doesn't include investments?

Depot values require a **Plus subscription**. Without Plus the `sensor.finanzfluss_investment_total` sensor will be unavailable and the net worth will only reflect cash account balances.

### Sensors stop updating / show "Unavailable"?

1. Check the HA logs for authentication or connection errors.
2. If tokens have expired and auto-refresh fails (e.g. password changed), go to **Settings → Devices & Services → Finanzfluss → Configure** and enter your new credentials.
3. Verify that `hippoverse.finanzfluss.de` is reachable from your HA instance.

### How do I change my login credentials?

Open **Settings → Devices & Services → Finanzfluss → Configure** (the Options Flow). Enter your new email and/or password. The integration will re-authenticate immediately and update all stored tokens.

---

## 🧑‍💻 Development

This project uses modern Python development tools:
- `ruff` for linting and formatting
- `mypy` for static type checking
- `pytest` for unit testing

### Setup

```bash
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements_test.txt
```

### Pre-commit checks

Before submitting a PR, run all quality checks:

```bash
ruff check . --fix
ruff format .
mypy .
pytest
```

---

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
