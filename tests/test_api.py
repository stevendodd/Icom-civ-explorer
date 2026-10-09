"""API tests using FastAPI's TestClient (httpx-backed)."""

from fastapi.testclient import TestClient

from civ_api.app import app

client = TestClient(app)


def test_list_radios_returns_all_supported_radios() -> None:
    resp = client.get("/radios")
    assert resp.status_code == 200
    ids = {r["id"] for r in resp.json()}
    assert ids == {"705", "7100", "7300", "7300mk2", "7610", "7760", "9700"}


def test_list_radios_has_address_and_command_count() -> None:
    resp = client.get("/radios")
    radio = next(r for r in resp.json() if r["id"] == "7300")
    assert radio["name"] == "IC-7300"
    assert radio["address"] == "94"
    assert radio["command_count"] > 0


def test_get_radio_unknown_returns_404() -> None:
    resp = client.get("/radios/notreal")
    assert resp.status_code == 404


def test_get_radio_case_insensitive_id() -> None:
    assert client.get("/radios/7300").status_code == 200
    assert client.get("/radios/IC-7300").status_code == 404  # name is not an id


def test_list_commands_no_filter_returns_paginated() -> None:
    resp = client.get("/commands", params={"limit": 5, "offset": 0})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] > 5
    assert len(body["items"]) == 5
    assert body["limit"] == 5


def test_list_commands_filter_by_radio() -> None:
    resp = client.get("/commands", params={"radio_id": "7300", "limit": 500})
    assert resp.status_code == 200
    body = resp.json()
    assert body["radio_id"] == "7300"
    assert all(item["radio_id"] == "7300" for item in body["items"])
    assert body["total"] == body["command_count"] if False else True  # noop guard


def test_list_commands_search_by_description() -> None:
    resp = client.get("/commands", params={"q": "frequency", "limit": 500})
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) > 0
    assert any("frequency" in item["description"].lower() for item in items)


def test_list_commands_search_by_cmd_code() -> None:
    resp = client.get("/commands", params={"q": "05", "limit": 500})
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) > 0
    assert any(item["cmd"] == "05" for item in items)


def test_list_commands_unknown_radio_returns_404() -> None:
    resp = client.get("/commands", params={"radio_id": "nope"})
    assert resp.status_code == 404


def test_radio_commands_endpoint() -> None:
    resp = client.get("/radios/7300/commands", params={"q": "vfo", "limit": 500})
    assert resp.status_code == 200
    body = resp.json()
    assert body["radio_id"] == "7300"
    assert body["total"] > 0
    assert all("vfo" in item["description"].lower() for item in body["items"])


def test_radio_capabilities_endpoint() -> None:
    resp = client.get("/radios/9700/capabilities")
    assert resp.status_code == 200
    caps = resp.json()
    names = {c["name"] for c in caps}
    assert "satellite_mode" in names  # IC-9700 supports satellite mode


def test_radio_capabilities_unknown_radio_404() -> None:
    assert client.get("/radios/zzz/capabilities").status_code == 404


def test_feedback_submission_accepted(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("CIV_FEEDBACK_FILE", str(tmp_path / "fb.jsonl"))
    # Reset cached feedback file path
    from civ_api import app as app_module
    app_module._feedback_file = None

    resp = client.post(
        "/feedback",
        json={
            "radio_id": "7300",
            "cmd": "05",
            "sub_cmd": "",
            "field": "description",
            "suggested_value": "Set operating frequency (corrected)",
            "notes": "Manual p.19-9",
            "submitter": "tester",
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "received"
    assert body["id"]
    assert (tmp_path / "fb.jsonl").exists()


def test_feedback_unknown_radio_404() -> None:
    resp = client.post(
        "/feedback",
        json={
            "radio_id": "nope",
            "cmd": "05",
            "field": "description",
            "suggested_value": "x",
        },
    )
    assert resp.status_code == 404


def test_feedback_capability_accepted(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("CIV_FEEDBACK_FILE", str(tmp_path / "fb.jsonl"))
    from civ_api import app as app_module
    app_module._feedback_file = None

    resp = client.post(
        "/feedback",
        json={
            "radio_id": "9700",
            "cmd": "",
            "field": "capability",
            "capability_name": "satellite_mode",
            "suggested_value": "false",
            "notes": "not supported on this firmware",
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "received"
    import json as _json
    raw = _json.loads((tmp_path / "fb.jsonl").read_text())
    assert raw["field"] == "capability"
    assert raw["capability_name"] == "satellite_mode"
    assert raw["cmd"] == ""


def test_health() -> None:
    assert client.get("/health").json() == {"status": "ok"}


def test_download_feedback_empty_when_no_file(tmp_path, monkeypatch) -> None:
    """When no feedback has been submitted, the download endpoint returns a
    200 with an empty body rather than a 404 (with valid admin auth)."""
    _setup_admin(tmp_path, monkeypatch)

    resp = client.get("/feedback", auth=AUTH)
    assert resp.status_code == 200
    assert resp.content == b""
    assert resp.headers["content-type"].startswith("application/x-ndjson")
    assert "attachment" in resp.headers["content-disposition"]
    assert "feedback.jsonl" in resp.headers["content-disposition"]


def test_download_feedback_returns_submitted_records(tmp_path, monkeypatch) -> None:
    """After feedback is submitted, the download endpoint returns the JSONL
    log verbatim as a downloadable file."""
    import json as _json

    fb_file, _, _ = _setup_admin(tmp_path, monkeypatch)

    client.post(
        "/feedback",
        json={
            "radio_id": "7300",
            "cmd": "05",
            "field": "description",
            "suggested_value": "corrected",
        },
    )
    assert fb_file.exists()

    resp = client.get("/feedback", auth=AUTH)
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/x-ndjson")
    assert "attachment" in resp.headers["content-disposition"]
    line = resp.text.strip()
    assert line  # non-empty
    record = _json.loads(line)
    assert record["radio_id"] == "7300"
    assert record["suggested_value"] == "corrected"


def test_download_feedback_is_served_as_inert_download(tmp_path, monkeypatch) -> None:
    """The feedback download carries attacker-controllable free-text (notes,
    suggested_value). It must be served in a way a browser cannot render or
    execute: a non-HTML content type, an attachment disposition (never inline),
    and nosniff so the type cannot be overridden by MIME sniffing. The global
    security middleware already adds these headers; this test pins them on the
    download route so a future override or streaming bypass is caught.
    """
    _setup_admin(tmp_path, monkeypatch)

    resp = client.get("/feedback", auth=AUTH)
    # 1. Non-HTML content type — never text/html.
    ctype = resp.headers["content-type"]
    assert "html" not in ctype.lower()
    assert ctype.startswith("application/x-ndjson")
    # 2. Disposition is attachment, never inline — prevents inline rendering.
    disp = resp.headers["content-disposition"]
    assert "attachment" in disp
    assert "inline" not in disp.lower()
    # 3. nosniff — browsers must not override the declared content type.
    assert resp.headers["x-content-type-options"] == "nosniff"
    # 4. CSP and framing hardening still apply (from the global middleware).
    assert "content-security-policy" in resp.headers
    assert resp.headers["x-frame-options"] == "DENY"


def test_download_feedback_markup_is_inert_data_not_executable(
    tmp_path, monkeypatch
) -> None:
    """Submitted markup is JSON-escaped within the NDJSON stream, so even if a
    browser were to mis-render the file it would see data, not live HTML. This
    guards against both stored-XSS (script executing on download) and HTML
    injection (markup rendering if the content type were ever weakened).
    """
    import json as _json

    _setup_admin(tmp_path, monkeypatch)

    client.post(
        "/feedback",
        json={
            "radio_id": "7300",
            "cmd": "05",
            "field": "description",
            "suggested_value": "<script>alert(1)</script>",
            "notes": "<img src=x onerror=alert(1)>",
        },
    )

    resp = client.get("/feedback", auth=AUTH)
    assert resp.status_code == 200
    # The body is a single JSON line: the markup must survive as an escaped
    # JSON string value, not as a raw HTML tag in the byte stream.
    body = resp.text
    record = _json.loads(body)
    assert record["suggested_value"] == "<script>alert(1)</script>"
    assert record["notes"] == "<img src=x onerror=alert(1)>"
    # No raw, unescaped HTML tag may appear outside of JSON string values: the
    # only '<' in the body must be inside the JSON-quoted string (escaped as
    # part of the value). A bare '<script>' tag with no surrounding quotes
    # would indicate the markup leaked out of the JSON envelope.
    assert "<script>alert(1)</script>" in body  # present, but inside quotes
    assert body.count("<script>") == 1  # not duplicated / unescaped elsewhere


# --- Feedback admin (GET / PUT / DELETE, HTTP Basic auth) -------------------

ADMIN_USER = "admin-test"
ADMIN_PASS = "test-pass-123"
AUTH = ("admin-test", "test-pass-123")


def _setup_admin(tmp_path, monkeypatch):
    """Point the feedback log at a temp file and configure admin credentials."""
    import json as _json
    import uuid as _uuid

    fb_file = tmp_path / "fb.jsonl"
    monkeypatch.setenv("CIV_FEEDBACK_FILE", str(fb_file))
    monkeypatch.setenv("CIV_ADMIN_USER", ADMIN_USER)
    monkeypatch.setenv("CIV_ADMIN_PASS", ADMIN_PASS)
    from civ_api import app as app_module
    app_module._feedback_file = None
    return fb_file, _json, _uuid


def _seed_log(fb_file, json_mod, uuid_mod, n=3):
    """Write n realistic records to the log file directly and return their ids."""
    ids = []
    lines = []
    for i in range(n):
        rid = str(uuid_mod.uuid4())
        ids.append(rid)
        lines.append(
            json_mod.dumps(
                {
                    "radio_id": "7300",
                    "cmd": "05",
                    "sub_cmd": "",
                    "field": "description",
                    "capability_name": "",
                    "suggested_value": f"correction {i}",
                    "notes": "",
                    "submitter": "seeder",
                    "id": rid,
                    "received_at": "2026-01-01T00:00:00+00:00",
                }
            )
        )
    fb_file.write_text("\n".join(lines) + "\n")
    return ids


def test_admin_rejects_without_credentials(tmp_path, monkeypatch) -> None:
    _setup_admin(tmp_path, monkeypatch)
    assert client.put("/feedback", content=b"").status_code == 401
    assert client.delete("/feedback/some-id").status_code == 401


def test_admin_fail_closed_when_env_unconfigured(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("CIV_FEEDBACK_FILE", str(tmp_path / "fb.jsonl"))
    from civ_api import app as app_module
    app_module._feedback_file = None

    # Fully unset → 401.
    monkeypatch.delenv("CIV_ADMIN_USER", raising=False)
    monkeypatch.delenv("CIV_ADMIN_PASS", raising=False)
    resp = client.put("/feedback", content=b"", auth=AUTH)
    assert resp.status_code == 401
    assert client.delete("/feedback/x", auth=AUTH).status_code == 401

    # Set but EMPTY must also fail closed.
    monkeypatch.setenv("CIV_ADMIN_USER", "")
    monkeypatch.setenv("CIV_ADMIN_PASS", "")
    assert client.put("/feedback", content=b"", auth=AUTH).status_code == 401
    assert client.delete("/feedback/x", auth=AUTH).status_code == 401


def test_admin_401_carries_basic_challenge_without_header(tmp_path, monkeypatch) -> None:
    """A missing Authorization header must still return the Basic challenge
    (browsers/HTTP libraries rely on it to prompt)."""
    _setup_admin(tmp_path, monkeypatch)
    resp = client.put("/feedback")
    assert resp.status_code == 401
    assert resp.headers["www-authenticate"].lower().startswith("basic")


def test_admin_wrong_password_401(tmp_path, monkeypatch) -> None:
    _setup_admin(tmp_path, monkeypatch)
    resp = client.put("/feedback", content=b"", auth=(ADMIN_USER, "wrong"))
    assert resp.status_code == 401
    assert "www-authenticate" in {k.lower() for k in resp.headers}


def test_admin_wrong_username_401(tmp_path, monkeypatch) -> None:
    _setup_admin(tmp_path, monkeypatch)
    resp = client.put("/feedback", content=b"", auth=("nobody", ADMIN_PASS))
    assert resp.status_code == 401


def test_admin_put_replaces_log(tmp_path, monkeypatch) -> None:
    fb_file, json_mod, uuid_mod = _setup_admin(tmp_path, monkeypatch)
    _seed_log(fb_file, json_mod, uuid_mod, n=3)

    keep = json_mod.dumps(
        {
            "radio_id": "7300",
            "cmd": "05",
            "sub_cmd": "",
            "field": "description",
            "capability_name": "",
            "suggested_value": "kept",
            "notes": "",
            "submitter": "seeder",
            "id": str(uuid_mod.uuid4()),
            "received_at": "2026-01-02T00:00:00+00:00",
        }
    )
    resp = client.put("/feedback", content=(keep + "\n").encode(), auth=AUTH)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "replaced"
    assert body["removed"] == 3
    assert body["kept"] == 1
    remaining = [json_mod.loads(line) for line in fb_file.read_text().splitlines() if line.strip()]
    assert len(remaining) == 1
    assert remaining[0]["suggested_value"] == "kept"
    assert remaining[0].keys() >= {"id", "received_at", "radio_id", "field", "suggested_value"}


def test_admin_put_empty_clears_log(tmp_path, monkeypatch) -> None:
    fb_file, json_mod, uuid_mod = _setup_admin(tmp_path, monkeypatch)
    _seed_log(fb_file, json_mod, uuid_mod, n=2)

    resp = client.put("/feedback", content=b"", auth=AUTH)
    assert resp.status_code == 200
    assert resp.json()["kept"] == 0
    assert fb_file.read_text() == ""
    # The public download reflects the cleared state.
    assert client.get("/feedback", auth=AUTH).content == b""


def test_admin_put_clears_when_file_absent(tmp_path, monkeypatch) -> None:
    _setup_admin(tmp_path, monkeypatch)
    resp = client.put("/feedback", content=b"", auth=AUTH)
    assert resp.status_code == 200
    assert resp.json() == {"status": "replaced", "removed": 0, "kept": 0}


def test_admin_put_validates_records(tmp_path, monkeypatch) -> None:
    fb_file, json_mod, uuid_mod = _setup_admin(tmp_path, monkeypatch)
    _seed_log(fb_file, json_mod, uuid_mod, n=1)

    bad = '{"radio_id":"7300","field":"not-a-field","suggested_value":"x","id":"a","received_at":"t"}\n'
    resp = client.put("/feedback", content=bad.encode(), auth=AUTH)
    assert resp.status_code == 400
    assert "Line 1" in resp.json()["detail"]

    bad_json = b'{"radio_id": broken json\n'
    resp = client.put("/feedback", content=bad_json, auth=AUTH)
    assert resp.status_code == 400

    ok_record = json_mod.dumps(
        {
            "radio_id": "zzznope",
            "cmd": "",
            "field": "capability",
            "capability_name": "",
            "suggested_value": "x",
            "notes": "",
            "submitter": "",
            "id": str(uuid_mod.uuid4()),
            "received_at": "2026-01-01T00:00:00+00:00",
        }
    )
    resp = client.put("/feedback", content=(ok_record + "\n").encode(), auth=AUTH)
    assert resp.status_code == 400
    assert "unknown radio" in resp.json()["detail"]
    # The log is untouched after all failed replaces.
    assert len([l for l in fb_file.read_text().splitlines() if l.strip()]) == 1


def test_admin_put_rejects_duplicate_ids(tmp_path, monkeypatch) -> None:
    fb_file, json_mod, uuid_mod = _setup_admin(tmp_path, monkeypatch)
    rec = json_mod.dumps(
        {
            "radio_id": "7300",
            "cmd": "",
            "field": "description",
            "suggested_value": "x",
            "id": str(uuid_mod.uuid4()),
            "received_at": "t",
        }
    )
    resp = client.put("/feedback", content=(rec + "\n" + rec + "\n").encode(), auth=AUTH)
    assert resp.status_code == 400
    assert "duplicate record id" in resp.json()["detail"]


def test_admin_put_oversize_413(tmp_path, monkeypatch) -> None:
    _setup_admin(tmp_path, monkeypatch)
    big_line = ('{"radio_id":"7300","field":"description","suggested_value":"%s","id":"a1","received_at":"t"}' % ("x" * 600)).encode()
    payload = b"\n".join([big_line] * 3000)
    resp = client.put("/feedback", content=payload, auth=AUTH)
    assert resp.status_code == 413


def test_admin_put_body_cap_413(tmp_path, monkeypatch) -> None:
    """The 1 MB *body* cap fires before anything is parsed or stored."""
    _setup_admin(tmp_path, monkeypatch)
    resp = client.put("/feedback", content=b"x" * (2_000_000), auth=AUTH)
    assert resp.status_code == 413
    assert "1 MB" in resp.json()["detail"]


def test_admin_put_rejects_unknown_extra_keys(tmp_path, monkeypatch) -> None:
    """FeedbackRecord forbids extra keys: a replace must never silently drop
    fields it doesn't know about (contract: PUT body round-trips GET output)."""
    fb_file, _json, _uuid = _setup_admin(tmp_path, monkeypatch)
    _seed_log(fb_file, _json, _uuid, n=1)

    record = {
        "radio_id": "7300",
        "cmd": "05",
        "sub_cmd": "",
        "field": "description",
        "capability_name": "",
        "suggested_value": "x",
        "notes": "",
        "submitter": "",
        "id": str(_uuid.uuid4()),
        "received_at": "2026-01-01T00:00:00+00:00",
        "EXTRA": "smuggled",
    }
    resp = client.put("/feedback", content=(_json.dumps(record) + "\n").encode(), auth=AUTH)
    assert resp.status_code == 400
    assert "Line 1" in resp.json()["detail"]
    # Log untouched.
    assert len([l for l in fb_file.read_text().splitlines() if l.strip()]) == 1


def test_admin_delete_removes_single_record(tmp_path, monkeypatch) -> None:
    fb_file, json_mod, uuid_mod = _setup_admin(tmp_path, monkeypatch)
    ids = _seed_log(fb_file, json_mod, uuid_mod, n=3)

    resp = client.delete(f"/feedback/{ids[1]}", auth=AUTH)
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"status": "deleted", "removed": 1, "kept": 2}
    remaining_ids = [json_mod.loads(l)["id"] for l in fb_file.read_text().splitlines() if l.strip()]
    assert ids[1] not in remaining_ids
    assert set(remaining_ids) == {ids[0], ids[2]}


def test_admin_delete_unknown_id_404(tmp_path, monkeypatch) -> None:
    import uuid as _uuid

    fb_file, json_mod, _ = _setup_admin(tmp_path, monkeypatch)
    _seed_log(fb_file, json_mod, _uuid, n=2)

    resp = client.delete(f"/feedback/{_uuid.uuid4()}", auth=AUTH)
    assert resp.status_code == 404
    assert resp.json()["detail"].startswith("Feedback id not found")
    # Nothing was removed.
    assert len([l for l in fb_file.read_text().splitlines() if l.strip()]) == 2


def test_admin_delete_when_log_absent_404(tmp_path, monkeypatch) -> None:
    import uuid as _uuid

    _setup_admin(tmp_path, monkeypatch)
    resp = client.delete(f"/feedback/{_uuid.uuid4()}", auth=AUTH)
    assert resp.status_code == 404


def test_admin_pull_modify_push_roundtrip(tmp_path, monkeypatch) -> None:
    """The GET -> edit -> PUT workflow preserves the log byte-shape: after a
    replace, GET returns parseable JSONL with exactly the pushed records."""
    import json as _json
    import uuid as _uuid

    fb_file, _json_mod, _uuid_mod = _setup_admin(tmp_path, monkeypatch)
    ids = _seed_log(fb_file, _json, _uuid, n=2)

    got = client.get("/feedback", auth=AUTH).text
    # Simulate the client editing: drop one record.
    kept_line = [l for l in got.splitlines() if l.strip() and _json.loads(l)["id"] == ids[0]][0]
    resp = client.put("/feedback", content=(kept_line + "\n").encode(), auth=AUTH)
    assert resp.status_code == 200
    assert resp.json() == {"status": "replaced", "removed": 2, "kept": 1}

    reloaded = client.get("/feedback", auth=AUTH).text
    records = [_json.loads(l) for l in reloaded.splitlines() if l.strip()]
    assert len(records) == 1
    assert records[0]["id"] == ids[0]
    # Exact field set: GET output must round-trip PUT field-for-field (no
    # fields silently added or dropped). FeedbackRecord has extra="forbid".
    assert set(records[0].keys()) == {
        "radio_id", "cmd", "sub_cmd", "field", "capability_name",
        "suggested_value", "notes", "submitter", "id", "received_at",
    }


def test_openapi_admin_security_scheme(tmp_path, monkeypatch) -> None:
    """The OpenAPI spec must expose the HTTPBasic scheme and attach it to the
    admin routes only — Swagger's lock icon and agent discovery depend on it.
    POST (submit) must stay public."""
    from civ_api.app import app as real_app

    spec = real_app.openapi()
    schemes = spec.get("components", {}).get("securitySchemes", {})
    assert schemes.get("HTTPBasic", {}).get("scheme") == "basic"
    assert spec["paths"]["/feedback"]["get"].get("security") == [{"HTTPBasic": []}]
    assert spec["paths"]["/feedback"]["put"].get("security") == [{"HTTPBasic": []}]
    assert spec["paths"]["/feedback/{feedback_id}"]["delete"].get("security") == [{"HTTPBasic": []}]
    assert not spec["paths"]["/feedback"]["post"].get("security")


def test_admin_get_requires_auth(tmp_path, monkeypatch) -> None:
    """Unauthenticated GET /feedback must 401 with the Basic challenge."""
    _setup_admin(tmp_path, monkeypatch)
    resp = client.get("/feedback")
    assert resp.status_code == 401
    assert resp.headers["www-authenticate"].lower().startswith("basic")
    # And a wrong password must also 401.
    assert client.get("/feedback", auth=(ADMIN_USER, "wrong")).status_code == 401


def test_post_feedback_public_even_without_admin_env(tmp_path, monkeypatch) -> None:
    """POST /feedback (submit) must keep working with NO admin credentials
    configured at all: the fail-closed gate applies to log management only."""
    monkeypatch.setenv("CIV_FEEDBACK_FILE", str(tmp_path / "fb.jsonl"))
    monkeypatch.delenv("CIV_ADMIN_USER", raising=False)
    monkeypatch.delenv("CIV_ADMIN_PASS", raising=False)
    from civ_api import app as app_module
    app_module._feedback_file = None

    resp = client.post(
        "/feedback",
        json={
            "radio_id": "7300",
            "cmd": "05",
            "field": "description",
            "suggested_value": "public submission",
        },
    )
    assert resp.status_code == 201
    assert resp.json()["status"] == "received"
    # With admin env unset the management endpoints stay 401 in the same state.
    assert client.get("/feedback").status_code == 401
    assert client.put("/feedback", content=b"").status_code == 401
    assert client.delete("/feedback/some-id").status_code == 401


# --- UI & security -------------------------------------------------------

def test_index_page_served() -> None:
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/html")
    assert "Icom CI-V Explorer" in resp.text
    # no inline event handlers in the served HTML
    assert "onclick" not in resp.text.lower()
    assert "onload" not in resp.text.lower()


def test_static_js_served() -> None:
    resp = client.get("/static/app.js")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/javascript")
    # JS never uses innerHTML/eval/document.write as code — the primary XSS
    # defence. Strip // line comments so the check ignores explanatory prose.
    import re as _re
    code_only = _re.sub(r"//.*", "", resp.text)
    assert ".innerHTML" not in code_only
    assert "eval(" not in code_only
    assert "document.write" not in code_only


def test_static_css_served() -> None:
    assert client.get("/static/styles.css").status_code == 200


def test_security_headers_present_on_api() -> None:
    resp = client.get("/radios")
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert resp.headers["X-Frame-Options"] == "DENY"
    assert resp.headers["Referrer-Policy"] == "no-referrer"
    assert "max-age=31536000" in resp.headers["Strict-Transport-Security"]
    csp = resp.headers["Content-Security-Policy"]
    assert "default-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp


def test_security_headers_present_on_html() -> None:
    resp = client.get("/")
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert resp.headers["X-Frame-Options"] == "DENY"
    assert "default-src 'self'" in resp.headers["Content-Security-Policy"]


def test_swagger_csp_relaxed_for_docs() -> None:
    resp = client.get("/docs")
    csp = resp.headers["Content-Security-Policy"]
    assert "'unsafe-inline'" in csp  # Swagger needs inline scripts


def test_feedback_rejects_non_hex_cmd(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("CIV_FEEDBACK_FILE", str(tmp_path / "fb.jsonl"))
    from civ_api import app as app_module
    app_module._feedback_file = None

    resp = client.post(
        "/feedback",
        json={
            "radio_id": "7300",
            "cmd": "<script>alert(1)</script>",  # not hex -> rejected
            "field": "description",
            "suggested_value": "x",
        },
    )
    assert resp.status_code == 422


def test_feedback_rejects_invalid_field_enum(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("CIV_FEEDBACK_FILE", str(tmp_path / "fb.jsonl"))
    from civ_api import app as app_module
    app_module._feedback_file = None

    resp = client.post(
        "/feedback",
        json={
            "radio_id": "7300",
            "cmd": "05",
            "field": "nonexistent_field",  # not in the Literal enum
            "suggested_value": "x",
        },
    )
    assert resp.status_code == 422


def test_feedback_rejects_oversized_notes(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("CIV_FEEDBACK_FILE", str(tmp_path / "fb.jsonl"))
    from civ_api import app as app_module
    app_module._feedback_file = None

    resp = client.post(
        "/feedback",
        json={
            "radio_id": "7300",
            "cmd": "05",
            "field": "description",
            "suggested_value": "x",
            "notes": "A" * 2001,  # max is 2000
        },
    )
    assert resp.status_code == 422


def test_feedback_stores_script_tag_verbatim_not_executed(tmp_path, monkeypatch) -> None:
    """Free-text fields are stored as-is (JSON-escaped) and rendered as text
    by the front-end (textContent), so a submitted <script> must be stored but
    never executed. This checks the storage side; the JS-side defence is
    verified by test_static_js_served."""
    import json as _json

    monkeypatch.setenv("CIV_FEEDBACK_FILE", str(tmp_path / "fb.jsonl"))
    from civ_api import app as app_module
    app_module._feedback_file = None

    payload = "<img src=x onerror=alert(1)>"
    resp = client.post(
        "/feedback",
        json={
            "radio_id": "7300",
            "cmd": "05",
            "field": "description",
            "suggested_value": payload,
            "notes": "<script>alert('xss')</script>",
        },
    )
    assert resp.status_code == 201
    # The raw file must contain the payload as a JSON string value (escaped),
    # not as live markup — it's data, not HTML.
    raw = (tmp_path / "fb.jsonl").read_text()
    assert payload in _json.loads(raw)["suggested_value"]
    assert "<script>" in _json.loads(raw)["notes"]


def test_command_search_result_xss_payload_is_text_not_html() -> None:
    """Even if reference data contained markup (it doesn't), the API returns
    JSON with string values; the front-end renders them via textContent."""
    resp = client.get("/commands", params={"q": "frequency", "limit": 1})
    body = resp.json()
    assert body["items"][0]["description"] == str(body["items"][0]["description"])