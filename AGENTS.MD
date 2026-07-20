# AI Agent Reference for ha-finanzfluss

---

## Token Efficiency Rules (CRITICAL - Read First)

These rules apply to **every response** without exception:

1. **Output minimal prose.** Bullet points only. No introductory sentences, no filler, no "Great question!", no "As requested".
2. **No walkthrough unless explicitly asked.** Never create or update `walkthrough.md` unless the user writes "walkthrough" or "summary" in their request.
3. **No implementation plan unless complex.** Skip planning artifacts for simple tweaks, single-file edits, bug fixes, or minor features. Plan only for major architectural changes.
4. **Short change summaries only.** After making changes, output <=5 bullet points describing *what* changed and *why* - never a line-by-line description.
5. **No repeating file content.** Never echo back code you just wrote or edited. Reference filenames with links instead.
6. **No tool-call narration.** Do not describe what tool you are about to call. Just call it.
7. **Targeted file reads only.** Use `grep_search` or `view_file` with `StartLine`/`EndLine` to read only the relevant section.
8. **Skip trivial confirmations.** Do not ask "Would you like me to proceed?" for obvious next steps. Just do them.
9. **No closing pleasantries.** End your response after the change summary.
10. **Suppress test output noise.** When running pytest, only report failures. Do not paste successful test output unless the user asks.

---

## Codebase Architecture

| Area | Path |
|---|---|
| Integration Entry | `custom_components/finanzfluss/__init__.py` |
| API Client | `custom_components/finanzfluss/api.py` |
| Coordinator | `custom_components/finanzfluss/coordinator.py` |
| Config/Options Flow | `custom_components/finanzfluss/config_flow.py` |
| Sensors | `custom_components/finanzfluss/sensor.py` |
| Constants | `custom_components/finanzfluss/const.py` |
| Brand Assets | `custom_components/finanzfluss/brand/` |
| Tests | `tests/` |
| Workflows | `.github/workflows/` |

---

## CLI Commands

| Task | Command | Dir |
|---|---|---|
| Run tests | `pytest` | Root |
| Ruff linter | `ruff check . --fix` | Root |
| mypy linter | `mypy .` | Root |

---

## Coding Rules

- **Traceback Preservation**: NEVER use `raise e`. ALWAYS use `raise ... from e` or a naked `raise` to prevent stack trace destruction.
- **Silent Failure Prohibition**: `except: pass` is FORBIDDEN. All exceptions must be wrapped and propagated, or logged with context.
- **Async HA Patterns**: Ensure all Home Assistant async updates are correctly handled (e.g. using `async_write_ha_state`).
- **Anti-Ban Compliance**: Never reduce jitter or bypass backoff logic. The 5-30s random delay before API calls is mandatory.

---

## API Notes

| Endpoint | Auth Required | Notes |
|---|---|---|
| `POST /v3/auth/login` | No | Returns `ffAccessToken`, `wapiAccessToken`, `refreshToken` |
| `POST /v2/auth/refreshAuth?refresh_token=...` | No | Refreshes all tokens |
| `GET /v3/accounts` | FF + WAPI Bearer | Returns all user accounts |
| `GET /v5/budgetBuckets/monthlyOverview?month=YYYY-MM-01` | FF Bearer | Monthly budget overview |
| `GET /v1/inflation?startDate=...&endDate=...` | FF Bearer | Inflation data rows |

Base URL: `https://hippoverse.finanzfluss.de/api`
