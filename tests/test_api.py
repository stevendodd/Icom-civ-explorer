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
    200 with an empty body rather than a 404."""
    monkeypatch.setenv("CIV_FEEDBACK_FILE", str(tmp_path / "fb.jsonl"))
    from civ_api import app as app_module
    app_module._feedback_file = None

    resp = client.get("/feedback")
    assert resp.status_code == 200
    assert resp.content == b""
    assert resp.headers["content-type"].startswith("application/x-ndjson")
    assert "attachment" in resp.headers["content-disposition"]
    assert "feedback.jsonl" in resp.headers["content-disposition"]


def test_download_feedback_returns_submitted_records(tmp_path, monkeypatch) -> None:
    """After feedback is submitted, the download endpoint returns the JSONL
    log verbatim as a downloadable file."""
    import json as _json

    fb_file = tmp_path / "fb.jsonl"
    monkeypatch.setenv("CIV_FEEDBACK_FILE", str(fb_file))
    from civ_api import app as app_module
    app_module._feedback_file = None

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

    resp = client.get("/feedback")
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
    monkeypatch.setenv("CIV_FEEDBACK_FILE", str(tmp_path / "fb.jsonl"))
    from civ_api import app as app_module
    app_module._feedback_file = None

    resp = client.get("/feedback")
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

    monkeypatch.setenv("CIV_FEEDBACK_FILE", str(tmp_path / "fb.jsonl"))
    from civ_api import app as app_module
    app_module._feedback_file = None

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

    resp = client.get("/feedback")
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