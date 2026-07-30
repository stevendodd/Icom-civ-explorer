"""FastAPI application: HTTPS REST API for the Icom CI-V protocol."""

from __future__ import annotations

import json
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from importlib import resources
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, status
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from .models import (
    Capability,
    CommandListResponse,
    FeedbackAck,
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
        "Feedback/corrections can be submitted for review."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(SecurityHeadersMiddleware)

_store: DataStore | None = None
_feedback_file: Path | None = None


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
    import os

    global _feedback_file
    if _feedback_file is None:
        env = os.environ.get("CIV_FEEDBACK_FILE")
        if env:
            _feedback_file = Path(env)
        else:
            _feedback_file = get_store().data_dir / "feedback.jsonl"
    return _feedback_file


def _static_dir() -> Path:
    """Return the bundled static UI directory."""
    with resources.as_file(resources.files("civ_api").joinpath("static")) as p:
        return Path(p)


@app.get("/", include_in_schema=False)
def index():
    """Serve the single-page web UI (API docs + interactive browser forms)."""
    return FileResponse(_static_dir() / "index.html", media_type="text/html")


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

    The API is read-only; this is the single write path. Submissions are
    appended to a JSONL file for later review and never mutate the reference
    data. The radio must exist; the command need not (it may be a missing
    entry being reported).
    """
    store = get_store()
    if store.get_radio(submission.radio_id.lower()) is None:
        raise HTTPException(
            status_code=404, detail=f"Unknown radio id: {submission.radio_id}"
        )
    record = submission.model_dump()
    record["id"] = str(uuid.uuid4())
    record["received_at"] = datetime.now(timezone.utc).isoformat()
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


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok"}