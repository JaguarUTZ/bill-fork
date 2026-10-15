import json
import socket
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from web import server as web_server


def _start(monkeypatch):
    server = web_server.ThreadingHTTPServer(("127.0.0.1", 0), web_server.DockHandler)
    port = server.server_address[1]
    monkeypatch.setattr(web_server, "PORT", port)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, port


def _request(port, path, *, method="GET", body=None, headers=None):
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = Request(
        f"http://127.0.0.1:{port}{path}",
        data=data,
        method=method,
        headers=headers or {},
    )
    try:
        with urlopen(request, timeout=2) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        payload = exc.read().decode("utf-8")
        parsed = json.loads(payload) if payload else {}
        return exc.code, parsed


def test_session_gates_posts_and_hides_the_confirmation_phrase(monkeypatch):
    web_server._state["pending"] = {
        "id": "plan-123",
        "confirmation_phrase": "CONFIRM secret",
    }
    server, port = _start(monkeypatch)
    token = web_server._session_token
    try:
        hidden = _request(port, "/api/bill")
        assert hidden[0] == 200
        assert "confirmation_phrase" not in hidden[1]["pending"]

        revealed = _request(
            port,
            "/api/bill",
            headers={"X-Dock-Session": token},
        )
        assert revealed[1]["pending"]["confirmation_phrase"] == "CONFIRM secret"

        rejected = _request(
            port,
            "/api/cancel",
            method="POST",
            body={"id": "plan-123"},
            headers={"Content-Type": "application/json"},
        )
        assert rejected[0] == 401

        wrong_type = _request(
            port,
            "/api/cancel",
            method="POST",
            body={"id": "missing"},
            headers={
                "Content-Type": "text/plain",
                "X-Dock-Session": token,
            },
        )
        assert wrong_type[0] == 415

        foreign = _request(
            port,
            "/api/cancel",
            method="POST",
            body={"id": "missing"},
            headers={
                "Content-Type": "application/json",
                "X-Dock-Session": token,
                "Origin": "http://evil.example",
            },
        )
        assert foreign[0] == 403

        page = urlopen(f"http://127.0.0.1:{port}/", timeout=2)
        html = page.read().decode("utf-8")
        assert f'content="{token}"' in html
    finally:
        web_server._state["pending"] = None
        server.shutdown()
        server.server_close()


def test_oversized_content_length_is_rejected_without_reading_the_body(monkeypatch):
    server, port = _start(monkeypatch)
    token = web_server._session_token
    try:
        sock = socket.create_connection(("127.0.0.1", port), timeout=2)
        request = (
            "POST /api/cancel HTTP/1.1\r\n"
            f"Host: 127.0.0.1:{port}\r\n"
            "Content-Type: application/json\r\n"
            f"X-Dock-Session: {token}\r\n"
            "Content-Length: 70000\r\n"
            "Connection: close\r\n"
            "\r\n"
        )
        sock.sendall(request.encode("ascii"))
        sock.settimeout(2)
        payload = sock.recv(2048).decode("utf-8", errors="replace")
        sock.close()
    finally:
        server.shutdown()
        server.server_close()

    assert "413" in payload
    assert "65536" in payload


def test_foreign_host_is_rejected(monkeypatch):
    server, port = _start(monkeypatch)
    try:
        status, payload = _request(
            port,
            "/api/health",
            headers={"Host": "evil.example"},
        )
    finally:
        server.shutdown()
        server.server_close()

    assert status == 403
    assert payload["ok"] is False
