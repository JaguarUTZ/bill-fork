"""No-radio HTTP path. No wallet, no radio, no Mutinynet coins."""

from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from web import server as web_server
from web.check_status import ACCEPTED_LABEL
from web.rgb.config import BillRole
from web.server import cors_headers, health_payload

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _restore_dock_state():
    saved = copy.deepcopy(web_server._state)
    saved_service = web_server._rgb_service
    yield
    with web_server._state_lock:
        web_server._state.clear()
        web_server._state.update(saved)
    web_server._rgb_service = saved_service


def test_cors_never_allows_a_star_or_an_unknown_origin(monkeypatch) -> None:
    monkeypatch.setenv("DOCK_CORS_ORIGIN", "*, https://fork.example/path")
    assert web_server._allowed_origins() == frozenset()
    assert cors_headers("*") == {}
    assert cors_headers("https://evil.example") == {}
    assert cors_headers(None) == {}

    monkeypatch.setenv("DOCK_CORS_ORIGIN", "https://fork.example, https://evil.example")
    allowed = cors_headers("https://fork.example")
    assert allowed["Access-Control-Allow-Origin"] == "https://fork.example"
    assert "*" not in allowed.values()
    assert cors_headers("https://other.example") == {}


def test_health_is_mutinynet_and_does_not_probe(monkeypatch) -> None:
    monkeypatch.setattr(web_server, "_rgb_service", object())
    payload = health_payload()
    assert payload["ok"] is True
    assert payload["network"] == "mutinynet"
    assert payload["mainnet"] is False
    assert payload["coins"] == "mutinynet-test-only"
    assert payload["indexer"] == "not-probed"
    assert payload["noradio"] is True
    assert payload["ble"] == "optional"


def _request(url: str, *, method: str = "GET", body: bytes | None = None, origin: str | None = None, content_length: int | None = None):
    headers = {}
    if origin:
        headers["Origin"] = origin
    if body is not None:
        headers["Content-Type"] = "application/json"
    if content_length is not None:
        headers["Content-Length"] = str(content_length)
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            raw = response.read()
            parsed = json.loads(raw.decode("utf-8")) if raw else {}
            return response.status, response.headers, parsed
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        parsed = json.loads(raw.decode("utf-8")) if raw else {}
        return exc.code, exc.headers, parsed


def test_http_cors_health_and_body_cap(monkeypatch) -> None:
    monkeypatch.setenv("DOCK_CORS_ORIGIN", "https://fork.example")
    monkeypatch.setattr(web_server, "MAX_JSON_BYTES", 8)
    monkeypatch.setattr(web_server, "_rgb_service", object())
    server = ThreadingHTTPServer(("127.0.0.1", 0), web_server.DockHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        status, headers, health = _request(
            base + "/api/health",
            origin="https://fork.example",
        )
        assert status == 200
        assert headers["Access-Control-Allow-Origin"] == "https://fork.example"
        assert health["mainnet"] is False
        assert health["network"] == "mutinynet"
        assert health["indexer"] == "not-probed"

        status, headers, _payload = _request(
            base + "/api/health",
            method="OPTIONS",
            origin="https://evil.example",
        )
        assert status == 204
        assert headers.get("Access-Control-Allow-Origin") is None

        status, _headers, payload = _request(
            base + "/api/noradio/plan",
            method="POST",
            body=b'{"cents":500,"invoice":"rgb:too-big"}',
            origin="https://fork.example",
        )
        assert status == 413
        assert payload["ok"] is False
    finally:
        server.shutdown()
        server.server_close()


def test_handlers_keep_accepted_funds_pending(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("CHECK_LEDGER_PATH", raising=False)
    monkeypatch.delenv("RGB_DATA_DIR", raising=False)
    sys.path.insert(0, str(ROOT))
    from scripts.e2e_check import MockDesk, _reset, _restore, _snapshot

    desk_b = MockDesk(BillRole.B, tmp_path)
    desk_a = MockDesk(BillRole.A, tmp_path)
    _reset("B", 0)
    invoice = web_server.handle_noradio_invoice(500, desk_b)
    saved = _snapshot()
    _reset("A", 6000)
    planned = web_server.handle_noradio_plan(500, invoice["handcarry"]["invoice"], desk_a)
    assert "confirmation_phrase" not in planned["pending"]
    wrong = web_server.handle_confirm(
        planned["pending"]["id"],
        "nope",
        desk_a,
        handcarry=True,
    )
    assert wrong["ok"] is False
    assert desk_a.confirm_calls == 0
    assert "handcarry" not in wrong
    sent = web_server.handle_confirm(
        planned["pending"]["id"],
        "CONFIRM " + planned["pending"]["id"],
        desk_a,
        handcarry=True,
    )
    assert sent["bill"]["cents"] == 5500
    _restore(saved)
    accepted = web_server.handle_noradio_import(sent["handcarry"]["body"], desk_b)
    assert accepted["bill"]["cents"] == 0
    assert accepted["bill"]["pending_cents"] == 500
    incoming = accepted["bill"]["checks"][0]
    assert incoming["label"] == ACCEPTED_LABEL
    assert incoming["counts_toward_spendable"] is False


def test_e2e_script_reports_the_labeled_mock() -> None:
    env = os.environ.copy()
    env["E2E_FORCE_MOCK"] = "1"
    env.pop("E2E_LIVE", None)
    env.pop("E2E_URL_A", None)
    env.pop("E2E_URL_B", None)
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "e2e_check.py")],
        check=False,
        capture_output=True,
        text=True,
        env=env,
        cwd=ROOT,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    assert "E2E_NETWORK=mock" in result.stdout
    assert "MUTINYNET_TCP=not-probed" in result.stdout
    assert "spendable_unchanged=true" in result.stdout
    assert "coins_moved=0" in result.stdout
    assert ACCEPTED_LABEL in result.stdout
    assert "settle_state=SETTLED" in result.stdout


def test_e2e_live_without_urls_refuses() -> None:
    env = os.environ.copy()
    env["E2E_LIVE"] = "1"
    env.pop("E2E_FORCE_MOCK", None)
    env.pop("E2E_URL_A", None)
    env.pop("E2E_URL_B", None)
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "e2e_check.py")],
        check=False,
        capture_output=True,
        text=True,
        env=env,
        cwd=ROOT,
        timeout=15,
    )
    assert result.returncode == 2, result.stdout + result.stderr
    assert "E2E_NETWORK=refused" in result.stdout
    assert "coins_moved=0" in result.stdout
