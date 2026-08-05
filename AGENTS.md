<!-- mulch:start -->
## Project Expertise (Mulch)
<!-- mulch-onboard-v:1 -->

This project uses [Mulch](https://github.com/jayminwest/mulch) for structured expertise management.

**At the start of every session**, run:
```bash
mulch prime
```

This injects project-specific conventions, patterns, decisions, and other learnings into your context.
Use `mulch prime --files src/foo.ts` to load only records relevant to specific files.

**Before completing your task**, review your work for insights worth preserving — conventions discovered,
patterns applied, failures encountered, or decisions made — and record them:
```bash
mulch record <domain> --type <convention|pattern|failure|decision|reference|guide> --description "..."
```

Link evidence when available: `--evidence-commit <sha>`, `--evidence-bead <id>`

Run `mulch status` to check domain health and entry counts.
Run `mulch --help` for full usage.
Mulch write commands use file locking and atomic writes — multiple agents can safely record to the same domain concurrently.

### Before You Finish

1. Discover what to record:
   ```bash
   mulch learn
   ```
2. Store insights from this work session:
   ```bash
   mulch record <domain> --type <convention|pattern|failure|decision|reference|guide> --description "..."
   ```
3. Validate and commit:
   ```bash
   mulch sync
   ```
<!-- mulch:end -->

## Project: Icom CI-V Explorer

HTTPS REST API for the Icom CI-V protocol. Read-only reference covering
multiple Icom radios, with a single write path (`POST /feedback`) for
user-submitted corrections. Built with FastAPI + Pydantic.

## Commands

```bash
# Install (editable, with test extras)
python -m venv .venv && source .venv/bin/activate
pip install -e ".[test]"

# Run (HTTPS by default; auto-generates a self-signed dev cert on first run)
python -m civ_api                      # HTTPS on :8443
python -m civ_api --http               # plain HTTP (dev only)
CIV_CERT=srv.crt CIV_KEY=srv.key python -m civ_api   # custom cert

# Tests
pytest
```

## Architecture

- `src/civ_api/` — the package (single package, no subpackages).
  - `app.py` — FastAPI app and route handlers. Read-only except `/feedback`.
  - `store.py` — `DataStore`: loads radios, capabilities, and command tables into
    memory at startup; powers all search/filter. Built once, shared across requests.
    Strips Icom-manual page references (`See p. N`, `See pp. N and M`) from the
    `Data`/`Description` CSV columns at load time via `_strip_page_refs()` — never
    by editing the bundled `data/` files.
  - `models.py` — Pydantic response/request models (input validated: hex
    patterns, length caps, `field` enum on feedback).
  - `security.py` — `SecurityHeadersMiddleware`: CSP, nosniff, frame-deny,
    HSTS, referrer policy. Swagger gets a relaxed CSP via path check.
  - `__main__.py` — uvicorn entry point with HTTPS + auto dev-cert.
  - `data/` — bundled reference data (the source of truth). Loaded via
    `importlib.resources` so it works from an installed wheel, not just the repo.
  - `static/` — bundled web UI (`index.html`, `app.js`, `styles.css`,
    `theme.js`) served at `/`. JS uses `textContent` only (never `innerHTML`);
    no inline handlers. `theme.js` (loaded in `<head>`) applies a light/dark
    theme persisted in `localStorage` (`civ-theme`, default dark) via the
    external script only — CSP forbids inline scripts, so the theme applies
    on `DOMContentLoaded` (a brief pre-paint flash of the default dark theme
    is the trade-off). Docs `<pre>` blocks get a DOM-built copy button.
- `tests/` — `test_api.py` (endpoints + UI + security), `test_store.py` (loader).

## Data model

- `data/civ-radio-capabilities.json` — radio registry (id/name/CI-V address/csv
  filename) + capability matrix (per-radio bool/string support values). The
  radio registry drives which CSVs get loaded; do not add a radio without its
  CSV entry. Radio ids are lowercased short codes (`7300`, `7300mk2`).
  Each capability has: `name` (snake_case machine key), `label` (human-friendly
  Title Case display string), `description`, `command_evidence`, and `radios`
  (map of radio-id → bool or string). Hardware-spec capabilities
  (`radio_type`, `tx_bands`, `rx_coverage`, `max_power`, `modes`,
  `receiver_architecture`, `display`) are listed **first** in the array so
  they appear at the top of the capabilities table in the UI. Capabilities
  must be verified against CSV command evidence and/or Icom UK product pages
  (https://icomuk.co.uk/Amateur_Radio_Ham sub-pages) — contradictions with
  product pages are treated with high suspicion.
- `data/civ-command-table-<model>.csv` — per-radio CI-V command tables. Four
  quoted columns: `Cmd.`, `Sub cmd.`, `Data`, `Description`. Rows with an empty
  `Cmd.` are skipped during load (formatting artifacts).
- `data/civ-aux.md` — unified encoding reference (BCD frequency, modes, etc.).

## Conventions

- The API is **read-only**. `/feedback` is the only write path; it appends to a
  JSONL file (`CIV_FEEDBACK_FILE` env var overrides location) and never mutates
  the reference data or the in-memory index.
- Radio ids are case-normalized to lowercase on input; the model name
  (e.g. `IC-7300`) is **not** accepted as an id — use `7300`.
- Search (`q`) is case-insensitive substring matching across `cmd`,
  `sub_cmd`, `data`, and `description` — not a structured query language.
- **Keep docs in sync after any API/UI change.** Three surfaces must agree:
  the OpenAPI spec at `/openapi.json` (auto-generated — authoritative), the
  Swagger UI at `/docs` (renders from the spec), the in-UI docs table in
  `static/index.html` (Endpoints table + code examples + skill definition
  accordion), and the README.md API overview. Verify the endpoint list
  (`GET /radios`, `/radios/{id}`, `/radios/{id}/capabilities`, `/commands`,
  `/radios/{id}/commands`, `POST /feedback`, `GET /feedback`, `GET /health`),
  param names (`q`, `radio_id`, `limit`, `offset`), and response field names
  (radios: `id/name/address/command_count`; commands:
  `radio_id/cmd/sub_cmd/data/description`; capabilities:
  `name/label/description/command_evidence/radios`).
  - The dev HTTPS cert is generated into the OS temp dir on first run; do not
  commit cert/key files (`*.pem`, `*.key`, `*.crt` are gitignored).

## Gotchas

- `CIV_CERT`/`CIV_KEY` empty strings must be treated as unset — `Path(".")` is
  truthy and will cause `IsADirectoryError` in uvicorn's SSL loader.
- List endpoints cap `limit` at 500, but the IC-9700 has 542 loaded rows. Any
  client (including the Browse tab) must page (`offset`) to fetch them all — a
  single request drops the higher-numbered codes (`21`–`28` sort last).
- Command tables contain duplicate `cmd` codes across rows (each sub-command
  is its own row); don't dedupe by `cmd` alone — use `(radio_id, cmd, sub_cmd)`.