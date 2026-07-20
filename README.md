# Finanzfluss (for Home Assistant)

[![GitHub Release](https://img.shields.io/github/release/FaserF/ha-finanzfluss.svg?style=flat-square)](https://github.com/FaserF/ha-finanzfluss/releases)
[![Downloads (Current release)](https://img.shields.io/github/downloads/FaserF/ha-finanzfluss/latest/finanzfluss.zip?label=Downloads%20(Current%20release)&style=flat-square)](https://github.com/FaserF/ha-finanzfluss/releases)
[![License](https://img.shields.io/github/license/FaserF/ha-finanzfluss.svg?style=flat-square)](LICENSE)
[![hacs](https://img.shields.io/badge/HACS-custom-orange.svg?style=flat-square)](https://hacs.xyz)
[![Add to Home Assistant](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=finanzfluss)
[![CI Orchestrator](https://github.com/FaserF/ha-finanzfluss/actions/workflows/ci-orchestrator.yml/badge.svg)](https://github.com/FaserF/ha-finanzfluss/actions/workflows/ci-orchestrator.yml)

A secure, production-ready Home Assistant integration for your **Finanzfluss.de Copilot** account. Track your financial accounts, net worth, budgets, and inflation data in real-time with native support for Two-Factor Authentication (TOTP/MFA).

## 🧭 Quick Links

| | | | |
| :--- | :--- | :--- | :--- |
| [✨ Features](#-features) | [📦 Installation](#-installation) | [⚙️ Configuration](#️-configuration) | [🧱 Entities](#-entities) |
| [🛡️ Security](#-security--anti-ban) | [❓ FAQ](#-troubleshooting--faq) | [🧑‍💻 Development](#-development) | [📄 License](#-license) |

---

## ✨ Features

- **Multi-Account Tracking**:
  - Automatically discovers all your accounts (checking, savings, cash, credit cards, investments).
  - Exposes each account's balance and transaction details as individual sensors.
  - Attributes include account type, IBAN, bank name, last sync time, and more.
- **Total Net Worth**:
  - Dynamically calculates your total net worth across all active/non-hidden accounts in a single entity.
- **Budget Monitoring**:
  - **Total Budget**: Exposes your total monthly budget limit and total spent amount.
  - **Category Budgets**: Exposes spent amounts and limits for individual budget categories (buckets) like groceries, housing, entertainment, etc.
- **Inflation Rate**:
  - Provides the latest consumer price index and inflation rate statistics directly from Finanzfluss.
- **Two-Factor Authentication (TOTP)**:
  - Full native support for Multi-Factor Authentication (MFA) during the integration setup flow.
- **Security & Anti-Ban Protections**:
  - Ported anti-ban strategies to protect your account from rate-limiting and bans (see below).

---

## 🛡️ Security & Anti-Ban

To safeguard your credentials and prevent your account from being flagged or rate-limited, the integration includes:
- **Random Jitter Delay**: Waits a random interval (5 to 30 seconds) before sending requests to the API.
- **Domain-wide Serialization**: Prevents multiple entry instances from hitting the endpoints at the same time.
- **Persistent State Cache**: Saves last success metadata to prevent redundant API queries upon Home Assistant restarts.
- **Fail-safe Backoff**: Implements exponential backoff on errors (2 hours on 403/429 rate limits, 30 minutes on other network failures).

---

## 📦 Installation

### HACS (Recommended)
1. Go to HACS in Home Assistant, select **Integrations**.
2. Click the three dots in the top-right corner, select **Custom repositories**.
3. Add `https://github.com/FaserF/ha-finanzfluss` as a custom repository with category `Integration`.
4. Click **Install**.
5. Restart Home Assistant.

### Manual
1. Download the latest release `.zip` and extract it.
2. Copy the `custom_components/finanzfluss/` directory to your Home Assistant's `custom_components/` folder.
3. Restart Home Assistant.

---

## ⚙️ Configuration

1. In Home Assistant, go to **Settings** > **Devices & Services**.
2. Click **Add Integration** in the bottom right.
3. Search for **Finanzfluss** and select it.
4. Input your email and password.
5. If prompted, enter the 2FA code (TOTP) from your authenticator app.
6. The integration will automatically set up all sensors.

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
