#!/usr/bin/env python3
"""Feedback-admin client for the Icom CI-V Explorer site.

Manages the review queue (feedback.jsonl) served by GET/PUT/DELETE /feedback
on the live API. All three operations (download log, replace log, delete a
record) require HTTP Basic auth; credentials come from a local credentials
file that is never committed (gitignored).

Credentials file (first found wins):
  1. $CIV_ADMIN_CREDS
  2. .civ-admin.json in the current directory
  3. .civ-admin.json in any parent directory (repo root)

Format:
  {"username": "...", "password": "...", "base_url": "https://..."}

Examples:
  ./scripts/feedback_admin.py pull                 # GET /feedback -> feedback-live.jsonl
  ./scripts/feedback_admin.py list                 # summarize the live log
  ./scripts/feedback_admin.py rm <uuid> [<uuid>..] # delete records by id
  ./scripts/feedback_admin.py push                 # replace log with feedback-live.jsonl
  ./scripts/feedback_admin.py push /path/empty.jsonl --yes   # clear the log

Exit codes: 0 ok, 1 any HTTP or credential failure, 2 usage error.
The password is never printed.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
from pathlib import Path
from urllib import error, request

DEFAULT_CREDS_FILENAME = ".civ-admin.json"
DEFAULT_BASE_URL = "https://icom-civ.stevendodd.net"
DEFAULT_LOG_FILE = "feedback-live.jsonl"
TIMEOUT = 30


def _find_creds_file(explicit: str | None) -> Path | None:
    if explicit:
        return Path(explicit)
    env = os.environ.get("CIV_ADMIN_CREDS")
    if env:
        return Path(env)
    current = Path.cwd().resolve()
    while True:
        candidate = current / DEFAULT_CREDS_FILENAME
        if candidate.is_file():
            return candidate
        if current.parent == current:
            return None
        current = current.parent


def _warn_loose_permissions(path: Path) -> None:
    try:
        mode = path.stat().st_mode & 0o777
        if mode & 0o077:
            print(
                f"warning: {path} is mode {oct(mode)}; other users on this machine "
                "can read the admin password. Fix: chmod 600 " + str(path),
                file=sys.stderr,
            )
    except OSError:
        pass


def load_creds(explicit: str | None) -> tuple[str, str, str]:
    """Return (base_url, username, password); never prints the password."""
    path = _find_creds_file(explicit)
    if path is None:
        raise SystemExit(
            f"No credentials file found. Create {DEFAULT_CREDS_FILENAME} in the repo root "
            f'(gitignored) or set CIV_ADMIN_CREDS. Format: {{"username": "...", '
            '"password": "...", "base_url": "https://..."}}'
        )
    _warn_loose_permissions(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    username = data.get("username")
    password = data.get("password")
    if not username or not password:
        raise SystemExit(f"{path} must define non-empty 'username' and 'password'")
    return data.get("base_url") or DEFAULT_BASE_URL, username, password


def _auth_header(username: str, password: str) -> str:
    token = base64.b64encode(f"{username}:{password}".encode()).decode()
    return f"Basic {token}"


def _http(
    method: str,
    base_url: str,
    username: str,
    password: str,
    path: str = "/feedback",
    body: str | None = None,
) -> tuple[int, bytes]:
    headers = {"Authorization": _auth_header(username, password)}
    data = None
    if body is not None:
        data = body.encode("utf-8")
        headers["Content-Type"] = "application/x-ndjson"
    req = request.Request(base_url.rstrip("/") + path, data=data, headers=headers, method=method)
    try:
        with request.urlopen(req, timeout=TIMEOUT) as resp:
            return resp.status, resp.read()
    except error.HTTPError as exc:
        return exc.code, exc.read()


def _call(
    method: str,
    base_url: str,
    username: str,
    password: str,
    path: str = "/feedback",
    body: str | None = None,
) -> tuple[int, bytes] | None:
    """Call _http but report network-level failures (DNS/refused/timeout) as a
    clean one-line stderr message instead of a traceback. Returns None when the
    network is unreachable (no HTTP response at all)."""
    try:
        return _http(method, base_url, username, password, path, body)
    except error.URLError as exc:
        reason = getattr(exc, "reason", exc)
        print(f"error: {method} {base_url.rstrip('/')}{path}: network failure: {reason}", file=sys.stderr)
        return None
    except OSError as exc:
        print(f"error: {method} {base_url.rstrip('/')}{path}: network failure: {exc}", file=sys.stderr)
        return None


def _parse_ack(text: str) -> dict:
    try:
        ack = json.loads(text)
        return ack if isinstance(ack, dict) else {}
    except json.JSONDecodeError:
        return {}


def _body_text(content: bytes) -> str:
    return content.decode("utf-8", errors="replace").strip()


def _records(text: str) -> list[dict]:
    out = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"Received log is not valid JSONL: {exc}")
        out.append(obj)
    return out


def cmd_pull(args: argparse.Namespace) -> int:
    base_url, username, password = load_creds(args.creds)
    result = _call("GET", base_url, username, password)
    if result is None:
        return 1
    status_code, content = result
    if status_code != 200:
        print(f"error: GET /feedback -> HTTP {status_code}: {_body_text(content)}", file=sys.stderr)
        return 1
    out = Path(args.out)
    out.write_bytes(content)
    count = len(_records(_body_text(content)))
    print(f"{count} record(s) -> {out}")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    base_url, username, password = load_creds(args.creds)
    result = _call("GET", base_url, username, password)
    if result is None:
        return 1
    status_code, content = result
    if status_code != 200:
        print(f"error: GET /feedback -> HTTP {status_code}: {_body_text(content)}", file=sys.stderr)
        return 1
    records = _records(_body_text(content))
    if not records:
        print("(log is empty)")
        return 0
    for rec in records:
        cmd = rec.get("cmd") or "-"
        sub = rec.get("sub_cmd") or "-"
        subject = rec.get("capability_name") or f"{cmd}/{sub}"
        notes = (rec.get("notes") or rec.get("suggested_value") or "").replace("\n", " ")
        if len(notes) > 60:
            notes = notes[:57] + "..."
        print(
            f"{rec.get('id', '?')}  {rec.get('received_at', '?')[:19]}  "
            f"[{rec.get('radio_id', '?')} {rec.get('field', '?')} {subject}]"
            f"  {notes}"
        )
    return 0


def cmd_rm(args: argparse.Namespace) -> int:
    base_url, username, password = load_creds(args.creds)
    failed = 0
    for record_id in args.ids:
        result = _call("DELETE", base_url, username, password, path=f"/feedback/{record_id}")
        if result is None:
            failed = 1
            continue
        status_code, body = result
        if status_code == 200:
            ack = _parse_ack(_body_text(body))
            print(f"{record_id}: deleted ({ack.get('removed')} removed, {ack.get('kept')} kept)")
        else:
            print(f"{record_id}: HTTP {status_code}: {_body_text(body)}", file=sys.stderr)
            failed = 1
    return failed


def cmd_push(args: argparse.Namespace) -> int:
    base_url, username, password = load_creds(args.creds)
    src = Path(args.file)
    body = src.read_text(encoding="utf-8")
    # Local pre-flight so obvious mistakes never leave the machine.
    records = _records(body)
    ids = [rec.get("id") for rec in records if isinstance(rec, dict)]
    dups = {i for i in ids if ids.count(i) > 1}
    if dups:
        print(f"error: duplicate record ids in {src}: {sorted(dups)}", file=sys.stderr)
        return 1
    if not args.yes:
        print(f"about to replace the live log ({len(records)} record(s)) from {src}; rerun with --yes")
        return 0
    result = _call("PUT", base_url, username, password, body=body)
    if result is None:
        return 1
    status_code, content = result
    if status_code != 200:
        print(f"error: PUT /feedback -> HTTP {status_code}: {_body_text(content)}", file=sys.stderr)
        return 1
    ack = _parse_ack(_body_text(content))
    print(f"replaced: {ack.get('removed')} removed, {ack.get('kept')} kept")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--creds", help="Path to the credentials JSON (default: .civ-admin.json via cwd/parents or $CIV_ADMIN_CREDS)")
    sub = parser.add_subparsers(dest="command", required=True)

    p_pull = sub.add_parser("pull", help="Download the live feedback log to a local JSONL file")
    p_pull.add_argument("out", nargs="?", default=DEFAULT_LOG_FILE)
    p_pull.set_defaults(func=cmd_pull)

    p_list = sub.add_parser("list", help="Summarize the live feedback log")
    p_list.set_defaults(func=cmd_list)

    p_rm = sub.add_parser("rm", help="Delete records from the live log by id")
    p_rm.add_argument("ids", nargs="+")
    p_rm.set_defaults(func=cmd_rm)

    p_push = sub.add_parser("push", help="Replace the live feedback log with a local JSONL file")
    p_push.add_argument("file", nargs="?", default=DEFAULT_LOG_FILE)
    p_push.add_argument("--yes", action="store_true", help="Proceed with the replace (without this flag, push only prints its intent)")
    p_push.set_defaults(func=cmd_push)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())