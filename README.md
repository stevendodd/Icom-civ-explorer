# Icom CI-V Explorer

An HTTPS REST API for the Icom CI-V protocol. Read-only reference covering
multiple Icom radios, with a `POST /feedback` write path for user-submitted
corrections and admin-only Basic-auth endpoints for managing the feedback
log. Built with FastAPI + Pydantic.

## Supported radios

| ID       | Model        | Default CI-V address |
|----------|--------------|----------------------|
| `705`    | IC-705       | `A4`                 |
| `7100`   | IC-7100      | `88`                 |
| `7300`   | IC-7300      | `94`                 |
| `7300mk2`| IC-7300 MK2  | `B6`                 |
| `7610`   | IC-7610      | `98`                 |
| `7760`   | IC-7760      | `B2`                 |
| `9700`   | IC-9700      | `A2`                 |

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[test]"
```

## Run

```bash
python -m civ_api                      # HTTPS on :8443 (auto-generates a dev cert)
python -m civ_api --http               # plain HTTP on :8443 (dev only)
CIV_CERT=server.crt CIV_KEY=server.key python -m civ_api   # custom cert
```

- Browser UI: `https://localhost:8443/` — interactive forms for searching
  commands and submitting feedback, plus API documentation with code and
  AI-agent usage examples.
- Swagger UI: `https://localhost:8443/docs`
- OpenAPI spec: `https://localhost:8443/openapi.json`

## Architecture

A read-only API that serves Icom CI-V reference data for 7 radios, with a
write path (`POST /feedback`) for user corrections and a Basic-auth protected
admin path for managing the feedback log. No database — the reference data is
bundled CSV/JSON parsed once into memory at startup; feedback is appended to a
separate JSONL file.

### Startup flow

`python -m civ_api` runs `src/civ_api/__main__.py:main()`:

1. Parses args (`--http` flag, host/port, `CIV_CERT`/`CIV_KEY` env for custom
   certs).
2. If HTTPS (default) and no custom cert → generates a self-signed cert into the
   OS temp dir via `openssl` (cached for subsequent runs).
3. Starts uvicorn with the FastAPI app from `civ_api.app:app`.
4. FastAPI's lifespan handler calls `get_store()`, which builds the `DataStore`
   once and caches it in a module-level global.

### Data loading (`src/civ_api/store.py`)

`DataStore.default()` resolves the bundled `data/` dir via
`importlib.resources` (works from an installed wheel, not just the repo). At
construction:

1. Reads `data/civ-radio-capabilities.json` — the radio registry
   (id → name, CI-V address, CSV filename) + capability matrix.
2. For each radio entry, loads its `civ-command-table-<model>.csv` (4 quoted
   columns: `Cmd.`, `Sub cmd.`, `Data`, `Description`). Rows with empty `Cmd.`
   are skipped (formatting artifacts).
3. Builds three indexes in memory:
   - `radios: dict[id → RadioSummary]` — id, name, address, command count
   - `_by_radio: dict[id → list[Command]]` — per-radio command rows
   - `capabilities: list[Capability]` — cross-radio feature matrix
4. The full `commands` list is the concatenation of all per-radio rows
   (~3349 total).

The store is **built once** at startup and **shared across all requests**
(module-level `_store` global). It is never mutated — feedback writes go to a
separate JSONL file.

### Request handling (`src/civ_api/app.py`)

Routes call `get_store()` (returns cached singleton) and use its methods:

- `GET /radios` → `store.list_radios()` (canonical order)
- `GET /radios/{id}` → `store.get_radio(id.lower())` (404 if unknown)
- `GET /radios/{id}/capabilities` → `store.capabilities_for_radio(id)`
- `GET /commands?radio_id=&q=&limit=&offset=` → `store.search_commands()` —
  case-insensitive substring match across `cmd`, `sub_cmd`, `data`,
  `description`, and the embedded manual-note bodies; pagination via slice
- `GET /radios/{id}/commands?q=` → same, scoped to one radio
- Manual notes: rows embed `page_refs` (the manual page references the row's
  text cites) and `notes` (manual detail tables bound to the row — extracted
  from the reference PDFs' detail sections and table-page footnotes by
  `docs/icom manuals/extract_detail_panels.py` + `resolve_notes.py`, stored
  as `data/civ-command-notes-<id>.json`)
- `POST /feedback` → validates radio exists, appends a JSON record to
  `feedback.jsonl` (location via `CIV_FEEDBACK_FILE` env or bundled `data/`).
  **Never touches the in-memory index.**
- `GET /feedback` (admin) → downloads the JSONL log (HTTP Basic auth;
  empty log returns a 200 empty file).
- `PUT /feedback` (admin) → atomically replaces the whole feedback log after
  validating every record (HTTP Basic auth → `CIV_ADMIN_USER`/`CIV_ADMIN_PASS`).
- `DELETE /feedback/{id}` (admin) → atomically removes one record by id
  (HTTP Basic auth).
- `GET /` → serves `static/index.html`; `/static/*` → mounted `StaticFiles`

Every response passes through `SecurityHeadersMiddleware`
(`src/civ_api/security.py`), which attaches CSP, `nosniff`,
`X-Frame-Options: DENY`, `Referrer-Policy`, HSTS. Swagger `/docs` gets a
relaxed CSP.

### The write-path invariant

```
data/*.csv + *.json ──load──> DataStore (in-memory, immutable) ──> GET responses
                                                                     │
POST /feedback ──────────────────────────────────────────────────> feedback.jsonl (append)
GET /feedback (admin) ───────────────────────────────────────────> feedback.jsonl (download)
PUT /feedback (admin) ───────────────────────────────────────────> feedback.jsonl (atomic replace)
DELETE /feedback/{id} (admin) ───────────────────────────────────> feedback.jsonl (atomic remove)
```

The reference data is the source of truth, loaded once. Feedback is the only
mutable surface and is firewalled from it — writes go to a separate JSONL file
for later review, never mutating the index or the bundled data. Downloading,
replacing, and deleting log content are HTTP Basic-auth gated and fail closed
when `CIV_ADMIN_USER`/`CIV_ADMIN_PASS` are not configured.

### Storing data

There is no database. The "store" is:

- **Reads**: bundled CSV/JSON files in `src/civ_api/data/`, parsed once into the
  in-memory `DataStore` at startup.
- **Writes**: `feedback.jsonl` (one JSON object per line), created
  next to the bundled data by default or wherever `CIV_FEEDBACK_FILE` points.
  `POST` appends; the admin `PUT`/`DELETE` rewrite atomically (temp file +
  `os.replace`).

### Package layout

```
src/civ_api/
  app.py       — FastAPI app and route handlers (read-only except /feedback)
  store.py     — DataStore: loads radios, capabilities, command tables at startup
  models.py    — Pydantic response/request models (input validated: hex patterns,
                 length caps, field enum on feedback)
  security.py  — SecurityHeadersMiddleware: CSP, nosniff, frame-deny, HSTS
  __main__.py  — uvicorn entry point with HTTPS + auto dev-cert
  data/        — bundled reference data (the source of truth), loaded via
                 importlib.resources so it works from an installed wheel
  static/      — bundled web UI (index.html, app.js, styles.css) served at /
                 JS uses textContent only (never innerHTML); no inline handlers
scripts/
  feedback_admin.py — agent/CLI client for the admin feedback endpoints
                      (pull/list/rm/push; reads .civ-admin.json, gitignored)
tests/
  test_api.py  — endpoints + UI + security + admin-auth tests
  test_store.py — loader tests
```

## API overview

- `GET /radios` — list radios with default CI-V addresses and command counts
- `GET /radios/{radio_id}` — single radio info
- `GET /radios/{radio_id}/capabilities` — capabilities for a radio
- `GET /commands?radio_id=7300&q=frequency` — search/filter commands
- `GET /radios/{radio_id}/commands?q=vfo` — search within one radio
- `POST /feedback` — submit a correction for review
- `GET /feedback` — admin: download all submitted feedback as JSONL
  (HTTP Basic auth)
- `PUT /feedback` — admin: replace the whole feedback log (Basic auth; body
  is the same JSONL format GET returns; empty body clears the log)
- `DELETE /feedback/{id}` — admin: remove one feedback record (Basic auth)
- `GET /health` — health check

The query (`q`) matches against command code, sub-command, data payload, and
description (case-insensitive). The API is read-only except for the feedback
log (`CIV_FEEDBACK_FILE` overrides its location): `POST` appends (public),
while `GET`/`PUT`/`DELETE` require HTTP Basic auth against the
`CIV_ADMIN_USER` / `CIV_ADMIN_PASS` server environment variables and fail
closed (401) when they are unset. Admin operations are atomic; on failure the
log is untouched.

## Calling the API

### curl

```bash
curl -k https://localhost:8443/radios
curl -k "https://localhost:8443/commands?radio_id=7300&q=frequency&limit=10"
```

`-k` skips cert verification for the self-signed dev cert. Drop it when using
a real CA-signed certificate.

### Python (requests)

```python
import requests

BASE = "https://localhost:8443"
SESSION = requests.Session()
SESSION.verify = False  # dev cert only; use a real CA bundle in production

radios = SESSION.get(f"{BASE}/radios").json()
for r in radios:
    print(r["id"], r["name"], r["address"], r["command_count"])

hits = SESSION.get(f"{BASE}/radios/9700/commands", params={"q": "sat"}).json()
for c in hits["items"]:
    print(c["cmd"], c["sub_cmd"], c["description"])

caps = SESSION.get(f"{BASE}/radios/7300/capabilities").json()
for cap in caps:
    print(cap["name"], cap["radios"]["7300"])
```

### Python (httpx, async)

```python
import httpx

async with httpx.AsyncClient(base_url="https://localhost:8443", verify=False) as client:
    radios = (await client.get("/radios")).json()
    cmds  = (await client.get("/commands", params={"radio_id": "7300", "q": "vfo"})).json()
```

### JavaScript (fetch)

```javascript
const BASE = "https://localhost:8443";

const radios = await (await fetch(`${BASE}/radios`)).json();

const url = new URL(`${BASE}/commands`);
url.searchParams.set("radio_id", "7300");
url.searchParams.set("q", "frequency");
url.searchParams.set("limit", "50");
const result = await (await fetch(url)).json();
console.log(result.total, result.items);
```

### Submitting feedback

```bash
curl -k -X POST https://localhost:8443/feedback \
  -H "Content-Type: application/json" \
  -d '{"radio_id":"7300","cmd":"05","sub_cmd":"","field":"description",\
        "suggested_value":"Set operating frequency (corrected)",\
        "notes":"Manual p.19-9","submitter":"tester"}'
```

### Managing the feedback log (admin)

```bash
# Credentials: .civ-admin.json (repo root, gitignored), or pass --creds / set
# CIV_ADMIN_CREDS. Format: {"username": "...", "password": "...", "base_url": "https://..."}

# Agent/CLI workflow (stdlib client, no dependencies). All operations,
# including pull/list, authenticate with the stored credentials:
scripts/feedback_admin.py pull            # GET /feedback (admin) -> feedback-live.jsonl
scripts/feedback_admin.py list            # summarize the live log
scripts/feedback_admin.py rm <uuid>       # remove one record by id
scripts/feedback_admin.py push --yes      # replace the log from feedback-live.jsonl

# Raw curl equivalents:
curl -u "$USER:$PASS" https://localhost:8443/feedback > feedback.jsonl
curl -u "$USER:$PASS" -X PUT https://localhost:8443/feedback \
  -H "Content-Type: application/x-ndjson" --data-binary @feedback-live.jsonl
curl -u "$USER:$PASS" -X DELETE https://localhost:8443/feedback/<uuid>
```

## Using the API from an AI agent

The API is read-only (except the feedback write path) and returns structured
JSON, which makes it straightforward for an LLM/agent to call via HTTP tool
use. Recommended workflow:

1. **Discover** supported radios with `GET /radios` to get valid radio ids and
   addresses.
2. **Search** with `GET /commands?q=...` (and optionally `radio_id=...`) to
   find commands by functionality or code. `q` is plain substring matching —
   keep queries short.
3. **Drill down** with `GET /radios/{id}/capabilities` to check whether a
   feature is supported on a specific radio.
4. **Submit corrections** with `POST /feedback` when the agent finds a wrong or
   missing entry. Validate `radio_id` against `/radios` first.

### Example tool schema (OpenAI function-calling style, trimmed)

```json
{
  "name": "civ_search_commands",
  "description": "Search Icom CI-V commands across cmd/sub_cmd/data/description and manual note bodies. Returns JSON.",
  "parameters": {
    "type": "object",
    "properties": {
      "q":        {"type": "string", "description": "Free-text search, e.g. 'frequency'"},
      "radio_id": {"type": "string", "description": "Optional radio id: 705,7100,7300,7300mk2,7610,7760,9700"},
      "limit":    {"type": "integer", "minimum": 1, "maximum": 500, "default": 100},
      "offset":   {"type": "integer", "minimum": 0, "default": 0}
    }
  }
}
```

### Agent prompt guidance

- Always call `civ_list_radios` first to learn valid radio ids; never guess them.
- `radio_id` is a lowercase short code (e.g. `7300`), **not** the model name
  (`IC-7300`).
- If `q` returns too many rows, add `radio_id` to narrow, or increase `limit`
  (max 500).
- When reporting a command from the API, include the `radio_id`, `cmd`, and
  `sub_cmd` so the user can verify.
- Rows carry `page_refs` (the manual pages the row cites) and `notes` (the
  referenced manual tables as ASCII, e.g. the frequency data encoding). Each
  entry in `notes` may set `scope`: `"command"` when the manual annotates the
  command code itself (the note describes the whole command) or `"row"` when
  it annotates that data row. When a data cell says "see p. N", the
  corresponding table is usually already embedded in the row's `notes` —
  prefer quoting it over asking the user to find the manual.
- Only call `POST /feedback` when the user explicitly asks to submit a
  correction.
- If your agent framework reads an OpenAPI spec, point it at `/openapi.json`.
  The spec is self-describing and includes parameter constraints (hex patterns,
  length caps, enums) that help the agent construct valid requests.

## Security

- HTTPS by default (auto-generates a self-signed dev cert on first run).
- All responses carry defensive headers: `Content-Security-Policy`,
  `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy`,
  and `Strict-Transport-Security`. Swagger UI (`/docs`) gets a narrowly relaxed
  CSP so its inline scripts load.
- Feedback input is validated server-side: `cmd`/`sub_cmd` must match
  `^[0-9A-Fa-f]{1,4}$`, `field` is a fixed enum, and all free-text fields have
  length caps (see `src/civ_api/models.py`).
- Feedback-log admin operations (`GET`/`PUT`/`DELETE /feedback`) require HTTP
  Basic auth; `POST /feedback` (submit) stays public. Credentials are server
  environment variables (`CIV_ADMIN_USER` /
  `CIV_ADMIN_PASS`), comparison is constant-time (`secrets.compare_digest`),
  and admin calls return 401 when the variables are not configured (fail
  closed). Admin bodies are size- and record-capped, fully validated, and
  only applied atomically on full validation success.
- Admin credentials for clients live in a gitignored local file outside
  version control (`.civ-admin.json`); they are never committed or baked into
  container images (the Dockerfile contains no secrets).
- The web UI inserts all API-sourced text via `textContent` (never
  `innerHTML`), so stored markup in reference data or feedback cannot execute.
  No inline event handlers, `eval`, or `document.write`.

## Tests

```bash
pytest
```

62 tests covering endpoints, UI serving, security headers, XSS/injection
vectors, input validation, admin auth (and the public-POST pin), the data
loader, and the pull/modify/push feedback round-trip.

## Data sources

The reference data in `src/civ_api/data/`:

- `civ-command-table-<model>.csv` — per-radio CI-V command tables
- `civ-radio-capabilities.json` — radio registry and capability matrix
- `civ-aux.md` — unified encoding reference (BCD frequency, modes, etc.)

These files are the source of truth.

## License

MIT License with Attribution — see [LICENSE](LICENSE).

Free to use, modify, distribute, and sell (including commercial and closed-source
use). The only conditions are:

1. Keep the copyright + license notice in copies or substantial portions.
2. Include a visible attribution to the **Icom CI-V Explorer** project and its
   source repository (this repo) in your software's documentation, README, or
   an equivalent credits / about notice accessible to end users. For apps with a
   UI, a credits or about screen satisfies this requirement.

This is a permissive license — it does **not** require derivative works to be
open source.