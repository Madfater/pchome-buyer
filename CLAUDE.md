# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

A Playwright-based automation tool for buying limited-quantity products on PChome 24h (Taiwanese e-commerce site) the moment they go on sale ("搶購" / snap-up). The primary interface is a **web control panel** (React + Vite frontend, FastAPI backend); the CLI (`login` / `buy`) is an auxiliary tool. Each product is an independently startable job card; jobs sharing a sale time are merged at runtime into one run-group (one browser, one batched poll, one checkout).

## Commands

```bash
# Backend dependencies
uv sync

# Install Playwright's Chromium browser (required once)
uv run playwright install chromium

# Frontend: install deps and build (required before serving the panel from FastAPI)
npm --prefix frontend install
npm --prefix frontend run build

# Web control panel on http://127.0.0.1:8787 (serves frontend/dist)
uv run python main.py web [--port 9000] [--host 0.0.0.0]

# Frontend development: two terminals — backend + Vite dev server (proxies /api to :8787)
uv run python main.py web
npm --prefix frontend run dev

# CLI auxiliary commands
uv run python main.py login   # headed browser manual login → auth_state.json
uv run python main.py buy DGCQ39-A900JESMM [--headless] [--interval 0.3] \
    [--sale-time "2026-03-06 12:00"] [--lead 600]

# Checks (no test suite configured)
uv run --with pyright pyright pchome
npm --prefix frontend run lint    # oxlint
npm --prefix frontend run build   # includes tsc type check
```

## Architecture

`main.py` is a thin entry point → `pchome/cli.py`. The package is layered:

### `pchome/core/` — domain logic (no FastAPI, no persistence)

- **`config.py`** — `.env` loading, API endpoint URLs, polling constants, `AUTH_STATE_FILE` / `PRODUCTS_FILE` / `CHECKOUTS_FILE` paths, `get_cvc()` / `is_auto_pay()`.
- **`jsapi.py`** — browser-side JS snippets: `JSONP_JS` (shared JSONP helper; `{CB}` in a URL is replaced with a one-shot callback name) and `ADD_TO_CART_JS` (batch add-to-cart via `Promise.all`).
- **`timing.py`** — `now_ms()`, `parse_sale_time()` (raises `ValueError`), `get_server_offset()` (server−local clock offset, RTT-midpoint compensated).
- **`reporter.py`** — `Reporter` abstraction (`log` / `progress` / `product_status` / `phase`); `ConsoleReporter` for the CLI, `GroupReporter` (in `services/job_service.py`) pushes to SSE. Core modules never call `print()` directly. `phase()` reports run-group lifecycle to the service layer (default no-op).
- **`cancel.py`** — `JobCancelled` + `cancellable_sleep()`; web jobs are stopped via a `threading.Event` checked at every wait point.
- **`membership.py`** — `GroupMembership`: thread-safe mutable member set of a run-group. Members can join/leave during monitoring; `freeze()` locks the final list before add-to-cart (`add()` returns `False` afterwards).
- **`session.py`** — `login_flow(wait_for_user)` (headed browser, CLI-only), auth-state save/existence check, `check_session(page)` (loads the cart page and detects redirect to login; snapup/cart modify work without login — login is only enforced at checkout, so this runs before monitoring starts), `check_session_standalone()` (short-lived headless browser, used by the auth status endpoint).
- **`monitor.py`** — `wait_for_sale()`: polls the `prod/button` API (JSONP, one batched call for all products) for `ButtonType` (`ForSale` / `NotReady` / `SoldOut`) at `interval` ±50% randomized. Re-reads `membership.active_ids()` every loop iteration (dynamic join/leave); empty membership raises `JobCancelled`. Server time fetched once at start, resynced every 60s; every 60s fires a `no-cors` fetch to `ecssl-cart.pchome.com.tw` to keep the TLS connection warm. With a sale time, polls at `interval*4` until 15s before, then full speed.
- **`cart.py`** — `add_with_retry()` returns `(success_ids, failed_ids, results)` where `results` are structured `CartItemResult`s (incl. `PRODCOUNT`/`PRODTOTAL` from the cart-modify response). Per product: `snapup` API (fetch) returns a MAC auth code (**valid ~15 seconds**), immediately followed by `cart modify` (JSONP) with that MAC; all products in one `page.evaluate` via `Promise.all`. Retries failures up to 3 times (sold-out not retried).
- **`checkout.py`** — `go_to_checkout()` returns `CheckoutInfo`: cart → payinfo page, autofills CVC (multiple fallback selectors), optionally auto-clicks 確認付款 when `AUTO_PAY=true`, and captures order info **best-effort** (`_capture_payinfo`: selector cascade + truncated body text fallback; capture failures must never break the payment flow — the payinfo DOM selectors are unverified and may need live tuning).
- **`runner.py`** — `run_snapup_job(JobConfig, reporter, membership=, checkout_lock=, cancel=, hold=)`: lead sleep → launch browser → session check → monitor → freeze membership → add-to-cart retry → checkout → `hold(result)` (keeps browser open; called with the pending `JobResult` so the web layer can persist the checkout record while the browser is still open). Returns `JobResult(status, success_ids, cart_results, checkout)`. CLI passes no membership (a static one is built from `cfg.product_ids`).

### `pchome/services/` — application layer (state, threads, persistence)

- **`event_bus.py`** — `EventBus` fans events out to SSE subscriber queues (drops on full).
- **`product_store.py`** — `ProductStore`, persists `[{id, sale_time}]` to `products.json`.
- **`checkout_store.py`** — `CheckoutRecordStore`, persists checkout records to `checkouts.json` (newest first; `clear_completed()` removes only `completed: true`).
- **`product_id.py`** — `parse_product_ref()`: accepts a product-page URL (`…/prod/<ID>`) or a bare ID; single source of truth (frontend duplicates the regex only for input preview).
- **`auth_service.py`** — cookie import for remote deployment: `import_auth(payload)` auto-detects Playwright storage_state JSON vs browser-extension cookie arrays (Cookie-Editor / EditThisCookie; converts `expirationDate`→`expires`, normalizes `sameSite`, drops extension-only fields) and writes `auth_state.json`. `status(live=)` optionally runs `check_session_standalone()` (debounced 30s, only on explicit user action).
- **`job_service.py`** — the job/run-group model:
  - **Job** = one product card, states: `idle → queued → monitoring → forsale → carted → awaiting_payment → success`, branches `soldout / cart_failed / failed / session_expired / not_logged_in` (sticky), cancel → `idle` (restartable).
  - **RunGroup** = runtime entity, `gid = <sale_time-slug>#<seq>`, phases `pending → lead_wait → checking_session → monitoring → carting → checkout → holding → closed`. One thread + one browser per group (sync Playwright can't run on the asyncio loop).
  - `start(pids)`: buckets by sale_time; joins a live group in a joinable phase (`membership.add()`; `False` = just froze → new group) or spawns a new one. `cancel(pids)`: removes the member (empty group → cancel event closes the browser); a group in `holding` is released (closes browser) instead.
  - A **global checkout lock** serializes the add-to-cart→checkout phase across groups because the PChome cart is account-global.
  - `_hold()` writes the checkout record **before** blocking, so it's visible in the panel while the browser stays open; releasing the hold marks it completed.

### `pchome/api/` — FastAPI

- **`deps.py`** — `Container` (store/checkout_store/bus/jobs/auth singletons) built in `create_app()`, accessed via `request.app.state.container`; `Container.state()` is the full snapshot every mutating route returns.
- **`routers/`** — `products.py` (add by URL/ID, delete), `jobs.py` (`POST /api/jobs/start|cancel` with `{pids: []}`), `auth.py` (`POST /api/auth/import`, `GET /api/auth/status?live=`), `checkouts.py` (mark complete, clear completed), `events.py` (`GET /api/state`, `GET /api/events` SSE — sync generator; each subscribed tab holds a threadpool thread, acceptable for 1–2 tabs).
- **`app.py`** — `create_app()`: routers first, then mounts `frontend/dist` at `/` (`StaticFiles(html=True)`); returns a 503 hint if the frontend isn't built.
- SSE event types: `log`, `progress`, `job` (per-card `{pid, state, info, gid}`), `group` (`{gid, phase, member_pids}`; `closed` removes it), `checkout` (`{record}`).

### `frontend/` — React + TypeScript + Vite

- Only deps: react/react-dom; native `<dialog>`; plain CSS (`src/styles.css`, light/dark via `prefers-color-scheme`).
- `src/state.tsx` — single `useReducer` context mirroring `/api/state` + SSE patches; `useSse` refetches the snapshot on (re)connect to heal missed events. `src/api.ts` — fetch wrappers (mutations return the full snapshot). `src/types.ts` — backend contract types + label maps.
- `src/components/` — `TopBar` (auth badge + `LoginDialog` cookie paste/upload), `ProductGrid` (selection checkboxes + bulk bar + `AddProductDialog` URL/ID + datetime), `ProductCard` (開始/取消/結束 per state, group color stripe keyed by sale_time), `CheckoutGrid`/`CheckoutDetailDialog` (cart results table, payinfo capture, log tail, 標記完成/清除已完成), `LogPanel` (group-filterable).
- Vite dev server proxies `/api` to `127.0.0.1:8787` (`vite.config.ts`).

## Key design points to preserve when editing

- PChome's `prod/button` and `cart modify` endpoints are JSONP-only (cross-origin, no CORS) and must be called via injected `<script>` tags inside `page.evaluate` (`JSONP_JS`), not `fetch`. `snapup` and `datetime` have CORS enabled and use `fetch` directly.
- The product ID in URLs (e.g. `DGCQ39-A900JESMM`) is the store code (`DGCQ39`) plus item code; `add_to_cart_batch` derives `RS` (store ID) by splitting on `-` and appends `-000` for the cart's `TI` field.
- Multiple product IDs are monitored concurrently in a single polling loop (one batched `prod/button` call), not one browser page per product.
- Membership is frozen before add-to-cart (MAC 15s validity makes mid-cart mutation unsafe); never mutate a group's product set past the `carting` phase.
- Web jobs run **headless** (remote deployment). With `AUTO_PAY=false` a remote user cannot manually pay in the held browser — document/recommend `AUTO_PAY=true` for remote setups.
- `auth_state.json`, `.env` (CVC, AUTO_PAY), `products.json`, and `checkouts.json` are gitignored — never commit real values. The panel has **no auth layer**: default bind is 127.0.0.1; `--host 0.0.0.0` is allowed for remote deployment but must be protected by a reverse proxy (nginx basic auth / VPN / Cloudflare Access).

## Environment

Configured via `.env` (see `.env.example`):
- `CVC` — credit card security code, autofilled at checkout.
- `AUTO_PAY` — `true`/`false`; if `true`, auto-clicks the final payment confirmation button (recommended for remote/headless deployments).
