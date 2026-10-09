"""FastAPI application: HTTPS REST API for the Icom CI-V protocol."""

from __future__ import annotations

import json
import os
import secrets
import threading
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from importlib import resources
from pathlib import Path

from fastapi import Body, Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.responses import FileResponse, Response
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

from .models import (
    Capability,
    CommandListResponse,
    FeedbackAck,
    FeedbackMutationAck,
    FeedbackRecord,
    FeedbackSubmission,
    RadioSummary,
)
from .security import SecurityHeadersMiddleware
from .store import DataStore


@asynccontextmanager
async def lifespan(_app: FastAPI):
    get_store()
    yield


app = FastAPI(
    title="Icom CI-V Explorer",
    description=(
        "Read-only HTTPS REST API for the Icom CI-V protocol. Search CI-V "
        "commands by functionality or command code, filter by radio, and view "
        "top-level radio info (default transceiver IDs, capabilities). "
        "Feedback/corrections can be submitted for review. Feedback log "
        "administration (replace/delete) is available over HTTP Basic auth."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(SecurityHeadersMiddleware)

_store: DataStore | None = None
_feedback_file: Path | None = None
# Serializes feedback-log writes within this process: POST appends bound to
# the current inode while PUT/DELETE read-then-os.replace (new inode). Without
# the lock a POST landing between a replace's read and replace would vanish
# (fd writes into the unlinked inode). Assumes the single-process uvicorn
# deployment (threaded handlers, no multi-worker mode).
_feedback_lock = threading.Lock()
_admin_security = HTTPBasic(description="Feedback-admin credentials (server env CIV_ADMIN_USER / CIV_ADMIN_PASS)")

# Abuse guards for the admin replace operation.
_MAX_FEEDBACK_BODY_CHARS = 1_000_000
_MAX_FEEDBACK_RECORDS = 5000


def require_admin(credentials: HTTPBasicCredentials = Depends(_admin_security)) -> None:
    """HTTP Basic-auth gate for the feedback management endpoints.

    Credentials come from the ``CIV_ADMIN_USER`` / ``CIV_ADMIN_PASS`` server
    environment variables. Comparison is constant-time to resist timing
    analysis, and the gate **fails closed**: if either variable is unset (or
    empty), no request can authenticate and every admin call returns 401.
    """
    user = os.environ.get("CIV_ADMIN_USER", "")
    password = os.environ.get("CIV_ADMIN_PASS", "")
    if not user or not password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Feedback admin credentials are not configured on this server",
            headers={"WWW-Authenticate": "Basic"},
        )
    user_ok = secrets.compare_digest(credentials.username, user)
    pass_ok = secrets.compare_digest(credentials.password, password)
    if not (user_ok and pass_ok):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin credentials",
            headers={"WWW-Authenticate": "Basic"},
        )


def get_store() -> DataStore:
    global _store
    if _store is None:
        _store = DataStore.default()
    return _store


def get_feedback_file() -> Path:
    """Return the JSONL file used to persist feedback submissions.

    Defaults to ``data/feedback.jsonl`` next to the bundled reference data,
    but can be overridden via the ``CIV_FEEDBACK_FILE`` environment variable
    for deployments that want a writable location outside the package.
    """
    global _feedback_file
    if _feedback_file is None:
        env = os.environ.get("CIV_FEEDBACK_FILE")
        if env:
            _feedback_file = Path(env)
        else:
            _feedback_file = get_store().data_dir / "feedback.jsonl"
    return _feedback_file


def _replace_feedback_lines(path: Path, lines: list[str]) -> None:
    """Atomically replace the feedback log with the given JSONL lines.

    Writes to a uniquely named temp file in the same directory (same
    filesystem) and moves it into place with ``os.replace``, so a crash or
    concurrent reader can never observe a partially written log.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{uuid.uuid4().hex[:8]}.tmp")
    try:
        with tmp.open("w", encoding="utf-8") as fh:
            for line in lines:
                fh.write(line if line.endswith("\n") else line + "\n")
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def _static_dir() -> Path:
    """Return the bundled static UI directory."""
    with resources.as_file(resources.files("civ_api").joinpath("static")) as p:
        return Path(p)


@app.get("/", include_in_schema=False)
def index():
    """Serve the single-page web UI (API docs + interactive browser forms)."""
    return FileResponse(_static_dir() / "index.html", media_type="text/html")


@app.get("/sitemap.xml", include_in_schema=False)
def sitemap(request: Request):
    """Serve a sitemap with absolute URLs for search engine indexing.

    URLs are built from the incoming request so the sitemap is valid on any
    deployment host (sitemaps require absolute URLs per sitemaps.org).
    """
    # Build the base URL, honouring proxy forwarding headers so the sitemap
    # advertises the correct public scheme/host (e.g. https://...) when the
    # container serves plain HTTP behind a TLS-terminating reverse proxy.
    from urllib.parse import urlparse

    parsed = urlparse(str(request.base_url))
    scheme = request.headers.get("x-forwarded-proto", "").split(",")[0].strip() or parsed.scheme
    host = request.headers.get("x-forwarded-host", "").split(",")[0].strip() or parsed.netloc
    base = f"{scheme}://{host.rstrip('/')}"
    urls = [("/", 1.0, "monthly"), ("/docs", 0.7, "yearly"), ("/openapi.json", 0.6, "monthly")]
    body = ['<?xml version="1.0" encoding="UTF-8"?>',
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for path, priority, changefreq in urls:
        body.append("  <url>")
        body.append(f"    <loc>{base}{path}</loc>")
        body.append(f"    <changefreq>{changefreq}</changefreq>")
        body.append(f"    <priority>{priority}</priority>")
        body.append("  </url>")
    body.append("</urlset>")
    return Response(content="\n".join(body), media_type="application/xml")


@app.get("/robots.txt", include_in_schema=False)
def robots(request: Request):
    """Serve robots.txt, pointing crawlers at the sitemap.

    The Sitemap directive uses an absolute URL built from the request's
    forwarded headers so it advertises the correct public scheme/host.
    """
    from urllib.parse import urlparse

    parsed = urlparse(str(request.base_url))
    scheme = request.headers.get("x-forwarded-proto", "").split(",")[0].strip() or parsed.scheme
    host = request.headers.get("x-forwarded-host", "").split(",")[0].strip() or parsed.netloc
    base = f"{scheme}://{host.rstrip('/')}"
    body = "User-agent: *\nAllow: /\nSitemap: " + base + "/sitemap.xml\n"
    return Response(content=body, media_type="text/plain")


# Mount static assets (JS/CSS) under /static so the CSP can scope them.
app.mount("/static", StaticFiles(directory=str(_static_dir())), name="static")


@app.get("/radios", response_model=list[RadioSummary], tags=["radios"])
def list_radios() -> list[RadioSummary]:
    """List all supported radios with default CI-V addresses and command counts."""
    return get_store().list_radios()


@app.get("/radios/{radio_id}", response_model=RadioSummary, tags=["radios"])
def get_radio(radio_id: str) -> RadioSummary:
    store = get_store()
    radio = store.get_radio(radio_id.lower())
    if radio is None:
        raise HTTPException(status_code=404, detail=f"Unknown radio id: {radio_id}")
    return radio


@app.get(
    "/radios/{radio_id}/capabilities",
    response_model=list[Capability],
    tags=["radios"],
)
def get_radio_capabilities(radio_id: str) -> list[Capability]:
    store = get_store()
    radio = store.get_radio(radio_id.lower())
    if radio is None:
        raise HTTPException(status_code=404, detail=f"Unknown radio id: {radio_id}")
    return store.capabilities_for_radio(radio.id)


@app.get("/commands", response_model=CommandListResponse, tags=["commands"])
def list_commands(
    radio_id: str | None = Query(None, description="Filter to a single radio id"),
    q: str | None = Query(None, description="Search across cmd/sub_cmd/data/description"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> CommandListResponse:
    """List or search CI-V commands, optionally filtered by radio.

    The query ``q`` matches any of: command code, sub-command code, data
    payload description, or the human-readable description.
    """
    store = get_store()
    rid = radio_id.lower() if radio_id else None
    if rid and store.get_radio(rid) is None:
        raise HTTPException(status_code=404, detail=f"Unknown radio id: {radio_id}")
    items, total = store.search_commands(radio_id=rid, query=q, limit=limit, offset=offset)
    return CommandListResponse(
        radio_id=rid,
        query=q,
        total=total,
        limit=limit,
        offset=offset,
        items=items,
    )


@app.get(
    "/radios/{radio_id}/commands",
    response_model=CommandListResponse,
    tags=["commands"],
)
def list_radio_commands(
    radio_id: str,
    q: str | None = Query(None, description="Search within this radio's commands"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> CommandListResponse:
    """List commands for a specific radio, with optional search."""
    store = get_store()
    rid = radio_id.lower()
    if store.get_radio(rid) is None:
        raise HTTPException(status_code=404, detail=f"Unknown radio id: {radio_id}")
    items, total = store.search_commands(radio_id=rid, query=q, limit=limit, offset=offset)
    return CommandListResponse(
        radio_id=rid,
        query=q,
        total=total,
        limit=limit,
        offset=offset,
        items=items,
    )


@app.post(
    "/feedback",
    response_model=FeedbackAck,
    status_code=status.HTTP_201_CREATED,
    tags=["feedback"],
)
def submit_feedback(submission: FeedbackSubmission) -> FeedbackAck:
    """Submit a correction or comment on a command entry.

    The API is read-only; this is the single public write path (the feedback
    log can additionally be replaced/deleted via the admin endpoints).
    Submissions are appended to a JSONL file for later review and never
    mutate the reference data. The radio must exist; the command need not
    (it may be a missing entry being reported).
    """
    store = get_store()
    if store.get_radio(submission.radio_id.lower()) is None:
        raise HTTPException(
            status_code=404, detail=f"Unknown radio id: {submission.radio_id}"
        )
    record = submission.model_dump()
    record["id"] = str(uuid.uuid4())
    record["received_at"] = datetime.now(timezone.utc).isoformat()
    with _feedback_lock:
        path = get_feedback_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
    return FeedbackAck(id=record["id"], status="received", received_at=record["received_at"])


@app.get("/feedback", tags=["feedback"])
def download_feedback():
    """Download all submitted feedback as a JSONL file.

    Returns the accumulated feedback log (one JSON object per line) so it can
    be reviewed offline. If no feedback has been submitted yet, an empty file
    (200) is returned rather than a 404 — an empty log is a valid state.
    """
    path = get_feedback_file()
    if not path.exists():
        return Response(
            content=b"",
            media_type="application/x-ndjson",
            headers={"Content-Disposition": 'attachment; filename="feedback.jsonl"'},
        )
    return FileResponse(
        path=str(path),
        media_type="application/x-ndjson",
        filename="feedback.jsonl",
    )


def _ack(status_word: str, removed: int, kept: int) -> FeedbackMutationAck:
    return FeedbackMutationAck(status=status_word, removed=removed, kept=kept)


def _iter_feedback_lines(path: Path) -> list[str]:
    """Return the non-empty JSONL lines currently in the feedback log."""
    if not path.exists():
        return []
    return [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


@app.put(
    "/feedback",
    response_model=FeedbackMutationAck,
    status_code=status.HTTP_200_OK,
    tags=["feedback"],
)
def replace_feedback(
    payload: str = Body("", media_type="application/x-ndjson"),
    _admin: None = Depends(require_admin),
) -> FeedbackMutationAck:
    """Replace the entire feedback log with the submitted records.

    Admin endpoint (HTTP Basic auth). The body is the same NDJSON format the
    GET endpoint returns, so a pull/modify/push round-trip needs no
    conversion. Every line is validated against the FeedbackRecord model and
    every ``radio_id`` must exist, an id may not appear twice, and blank
    lines are tolerated. An empty body clears the log. The write is atomic.
    """
    if len(payload) > _MAX_FEEDBACK_BODY_CHARS:
        raise HTTPException(status_code=413, detail="Feedback log too large (1 MB limit)")
    records: list[FeedbackRecord] = []
    seen_ids: set[str] = set()
    store = get_store()
    for lineno, line in enumerate(payload.splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail=f"Line {lineno}: invalid JSON ({exc.msg})")
        if not isinstance(obj, dict):
            raise HTTPException(status_code=400, detail=f"Line {lineno}: record must be a JSON object")
        try:
            rec = FeedbackRecord.model_validate(obj)
        except ValidationError as exc:
            detail = "; ".join(f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}" for err in exc.errors())
            raise HTTPException(status_code=400, detail=f"Line {lineno}: invalid record ({detail})")
        if store.get_radio(rec.radio_id.lower()) is None:
            raise HTTPException(status_code=400, detail=f"Line {lineno}: unknown radio id: {rec.radio_id}")
        if rec.id in seen_ids:
            raise HTTPException(status_code=400, detail=f"Line {lineno}: duplicate record id: {rec.id}")
        seen_ids.add(rec.id)
        records.append(rec)
    if len(records) > _MAX_FEEDBACK_RECORDS:
        raise HTTPException(status_code=413, detail=f"Too many records (max {_MAX_FEEDBACK_RECORDS})")
    with _feedback_lock:
        path = get_feedback_file()
        removed = len(_iter_feedback_lines(path))
        _replace_feedback_lines(path, [json.dumps(rec.model_dump()) for rec in records])
    return _ack("replaced", removed=removed, kept=len(records))


@app.delete(
    "/feedback/{feedback_id}",
    response_model=FeedbackMutationAck,
    status_code=status.HTTP_200_OK,
    tags=["feedback"],
)
def delete_feedback(feedback_id: str, _admin: None = Depends(require_admin)) -> FeedbackMutationAck:
    """Remove a single feedback record by id.

    Admin endpoint (HTTP Basic auth). All other records are preserved
    verbatim; the rewrite is atomic. 404 if the id is unknown.
    """
    with _feedback_lock:
        path = get_feedback_file()
        kept_lines: list[str] = []
        removed = 0
        for line in _iter_feedback_lines(path):
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                obj = None
            record_id = obj.get("id") if isinstance(obj, dict) else None
            if record_id == feedback_id:
                removed += 1
            else:
                kept_lines.append(line)
        if removed == 0:
            raise HTTPException(status_code=404, detail=f"Feedback id not found: {feedback_id}")
        _replace_feedback_lines(path, kept_lines)
    return _ack("deleted", removed=removed, kept=len(kept_lines))


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok"}