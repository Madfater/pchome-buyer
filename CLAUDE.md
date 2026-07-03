# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

A Playwright-based automation tool for buying limited-quantity products on PChome 24h (Taiwanese e-commerce site) the moment they go on sale ("搶購" / snap-up). It has a CLI (`login` / `buy` / `web`) and a local web control panel (card grid, one card per product, products sharing a sale time are checked out together).

## Commands

```bash
# Install dependencies
uv sync

# Install Playwright's Chromium browser (required once)
uv run playwright install chromium

# Log in and save session to auth_state.json (opens a real browser, manual login)
uv run python main.py login

# Snap up one or more products (polls until sale opens, then adds to cart)
uv run python main.py buy DGCQ39-A900JESMM
uv run python main.py buy DGCQ39-A900JESMM DGCQ39-A900I4PN6 --headless --interval 0.3

# With a known sale time: sleeps until --lead (default 300s) before the sale,
# then polls at interval*4 until 15s before, then full speed
uv run python main.py buy DGCQ39-A900JESMM --sale-time "2026-03-06 12:00" [--lead 600]

# Web control panel on http://127.0.0.1:8787
uv run python main.py web [--port 9000]
```

There is no test suite, linter, or build step configured in this project.

## Architecture

`main.py` is a thin entry point; everything lives in the `pchome/` package:

- **`config.py`** — `.env` loading, API endpoint URLs, polling constants, `AUTH_STATE_FILE` / `PRODUCTS_FILE` paths, `get_cvc()` / `is_auto_pay()`.
- **`jsapi.py`** — browser-side JS snippets: `JSONP_JS` (shared JSONP helper; `{CB}` in a URL is replaced with a one-shot callback name) and `ADD_TO_CART_JS` (batch add-to-cart via `Promise.all`).
- **`timing.py`** — `now_ms()`, `parse_sale_time()` (raises `ValueError`), `get_server_offset()` (server−local clock offset, RTT-midpoint compensated).
- **`reporter.py`** — `Reporter` abstraction (`log` / `progress` / `product_status`); `ConsoleReporter` for the CLI, `WebReporter` (in `web/jobs.py`) pushes to SSE. Core modules never call `print()` directly.
- **`cancel.py`** — `JobCancelled` + `cancellable_sleep()`; web jobs are stopped via a `threading.Event` checked at every wait point.
- **`session.py`** — `login_flow(wait_for_user)` (headed browser, caller decides how to block: CLI uses `input()`, web uses `Event.wait()`), auth-state save/load, `check_session()` (loads the cart page and detects redirect to `ecvip.pchome.com.tw/login/...`; snapup/cart modify work without login — login is only enforced at checkout, so this runs before monitoring starts).
- **`monitor.py`** — `wait_for_sale()`: polls the `prod/button` API (JSONP, one batched call for all products) for `ButtonType` (`ForSale` / `NotReady` / `SoldOut`) at `interval` ±50% randomized. Server time fetched once at start, resynced every 60s; every 60s fires a `no-cors` fetch to `ecssl-cart.pchome.com.tw` to keep the TLS connection warm. With a sale time, polls at `interval*4` until 15s before, then full speed. Returns as soon as any product is `ForSale`; `[]` when all sold out.
- **`cart.py`** — `add_to_cart_batch()`: per product, `snapup` API (fetch) returns a MAC auth code (**valid ~15 seconds**), immediately followed by `cart modify` (JSONP) with that MAC; all products in one `page.evaluate` via `Promise.all`. `add_with_retry()` retries failures up to 3 times (sold-out not retried).
- **`checkout.py`** — `go_to_checkout()`: cart → payinfo page, autofills CVC (multiple fallback selectors), optionally auto-clicks 確認付款 when `AUTO_PAY=true`.
- **`runner.py`** — `run_snapup_job(JobConfig, reporter, checkout_lock=, cancel=, hold=)`: the full flow shared by CLI and web — lead sleep (replaces the old `schedule.sh`: if `sale_ts - now > lead`, sleep until lead) → launch browser → session check → monitor → add-to-cart retry → checkout → `hold()` (keeps browser open; CLI passes `input()`, web waits on the cancel event). Returns `JobResult(status, success_ids)`.
- **`cli.py`** — argparse + the three subcommands; all `input()`/`print()` interaction lives here.
- **`web/`** — FastAPI control panel (`main.py web`, binds 127.0.0.1):
  - `store.py` — `ProductStore`, persists product cards to `products.json`.
  - `jobs.py` — `JobManager`: groups products by `sale_time` (one group = one job = one browser context = one checkout); each job runs `run_snapup_job` in its own thread (sync Playwright can't run on the asyncio loop). A **global checkout lock** serializes the add-to-cart→checkout phase because the PChome cart is account-global. Login runs in a thread with a headed browser; the web UI's "save" button sets the event that `login_flow` waits on. `EventBus` fans events out to SSE subscriber queues.
  - `app.py` — routes (`/api/state`, `/api/products`, `/api/login/*`, `/api/jobs/*`, `/api/events` SSE via sync generator).
  - `static/index.html` — vanilla JS card grid; groups color-coded; live updates via `EventSource`.

Key design points to preserve when editing:
- PChome's `prod/button` and `cart modify` endpoints are JSONP-only (cross-origin, no CORS) and must be called via injected `<script>` tags inside `page.evaluate` (`JSONP_JS`), not `fetch`. `snapup` and `datetime` have CORS enabled and use `fetch` directly.
- The product ID in URLs (e.g. `DGCQ39-A900JESMM`) is the store code (`DGCQ39`) plus item code; `add_to_cart_batch` derives `RS` (store ID) by splitting on `-` and appends `-000` for the cart's `TI` field.
- Multiple product IDs are monitored concurrently in a single polling loop (one batched `prod/button` call), not one browser page per product.
- `auth_state.json` and `.env` (CVC, AUTO_PAY) are both gitignored — never commit real values from either. The web server must stay bound to 127.0.0.1 (no auth layer).

## Environment

Configured via `.env` (see `.env.example`):
- `CVC` — credit card security code, autofilled at checkout.
- `AUTO_PAY` — `true`/`false`; if `true`, auto-clicks the final payment confirmation button.
