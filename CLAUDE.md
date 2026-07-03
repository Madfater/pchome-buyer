# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

A Playwright-based automation script for buying limited-quantity products on PChome 24h (Taiwanese e-commerce site) the moment they go on sale ("搶購" / snap-up). It's a single-file CLI (`main.py`) with two commands: `login` (saves a browser session) and `buy` (polls a product's sale status and races to add it to the cart and check out).

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

# With a known sale time: polls at interval*4 until 15s before, then full speed
uv run python main.py buy DGCQ39-A900JESMM --sale-time "2026-03-06 12:00"

# Scheduled run: starts monitoring 5 minutes before a given sale time
./schedule.sh "2026-03-06 12:00" DGCQ39-A900IGZAX --headless
```

There is no test suite, linter, or build step configured in this project.

## Architecture

Everything lives in `main.py`, organized around the sale-day flow:

1. **`cmd_login`** — launches a non-headless browser, lets the user log in manually, then dumps `context.storage_state()` to `auth_state.json` (gitignored). All subsequent `buy` runs load this file instead of logging in again.
2. **`check_session`** — runs before monitoring starts: loads the cart page and detects the redirect to the login page (`ecvip.pchome.com.tw/login/...`), so an expired session fails fast instead of at sale time. Note: `snapup`/`cart modify` work without login; login is only enforced at checkout.
3. **`wait_for_sale`** — polls the `prod/button` API (a JSONP endpoint, called via `page.evaluate` + script injection since it's cross-origin) for each product's `ButtonType` (`ForSale` / `NotReady` / `SoldOut`). Runs at `--interval` seconds, randomized ±50% to avoid a fixed polling signature. Server time is fetched once at start (clock offset vs local, resynced every 60s) instead of every iteration. With `--sale-time`, polls at `interval*4` until 15s before the sale, then at full speed. Every 60s it fires a `no-cors` fetch to `ecssl-cart.pchome.com.tw` to keep the TLS connection warm for the snap-up moment. Returns as soon as *any* monitored product becomes `ForSale`; returns `[]` when all are `SoldOut`.
4. **`add_to_cart_batch`** — two-step add-to-cart that bypasses the UI, run for all ready products concurrently via `Promise.all` inside a single `page.evaluate`: calls the `snapup` API (via `fetch`) to get a MAC auth code (**valid ~15 seconds only**, so the follow-up must be immediate), then calls the `cart modify` API (JSONP, cross-origin) with that MAC to add the item. `cmd_buy` retries failed products up to 3 times; sold-out products are not retried.
5. **`go_to_checkout`** — navigates to the cart then the payinfo page, autofills the CVC field from the `CVC` env var (multiple fallback selectors), and optionally auto-clicks "確認付款" (confirm payment) if `AUTO_PAY=true`. The browser is left open afterward for manual confirmation/inspection.

Key design points to preserve when editing:
- PChome's `prod/button` and `cart modify` endpoints are JSONP-only (cross-origin, no CORS) and must be called via injected `<script>` tags inside `page.evaluate` (shared `JSONP_JS` helper, `{CB}` in the URL is replaced with a one-shot callback name), not `fetch`. `snapup` and `datetime` have CORS enabled and use `fetch` directly.
- The product ID in URLs (e.g. `DGCQ39-A900JESMM`) is the store code (`DGCQ39`) plus item code; `add_to_cart_batch` derives `RS` (store ID) by splitting on `-` and appends `-000` for the cart's `TI` field.
- Multiple product IDs are monitored concurrently in a single polling loop (one batched `prod/button` call), not one browser page per product.
- `auth_state.json` and `.env` (CVC, AUTO_PAY) are both gitignored — never commit real values from either.

## Environment

Configured via `.env` (see `.env.example`):
- `CVC` — credit card security code, autofilled at checkout.
- `AUTO_PAY` — `true`/`false`; if `true`, auto-clicks the final payment confirmation button.
