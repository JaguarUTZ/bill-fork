"""Create, accept, and settle one $5 check without a BLE puck.

Mutinynet is used only when ``E2E_LIVE=1`` and both ``E2E_URL_A`` and
``E2E_URL_B`` answer ``/api/health`` as Mutinynet with ``mainnet`` false.
Otherwise this runs a labeled mock through the real HTTP handlers and moves
no coins. ``E2E_FORCE_MOCK=1`` always selects the mock, including when a
live flag is also set.
"""

from __future__ import annotations

import json
import os
import socket
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dock.chunk_protocol import FrameKind  # noqa: E402
from web.check_status import ACCEPTED_LABEL  # noqa: E402
from web.rgb.adapter import ConsignmentArtifact, TransferPlan  # noqa: E402
from web.rgb.backend import ParsedInvoice  # noqa: E402
from web.rgb.config import BillRole  # noqa: E402
from web.rgb.tap_flow import InvoiceTransferPlan, ReceivedArtifact, StoredArtifact  # noqa: E402
from web.rgb_web import HandcarryInvoice, HandcarrySend, ImportOutcome, RgbWebError  # noqa: E402
from web.server import (  # noqa: E402
    _state,
    _state_lock,
    handle_confirm,
    handle_noradio_import,
    handle_noradio_invoice,
    handle_noradio_plan,
    handle_refresh,
)


class MockDesk:
    """In-memory stand-in for one role wallet. It never opens rgb-lib."""

    def __init__(self, role: BillRole, directory: Path) -> None:
        self.role = role
        self.confirm_calls = 0
        self.imported = False
        self.settle = False
        self.payload = b"mock-consignment-not-a-real-transfer"
        invoice_path = directory / f"invoice-{role.value}.rgb-invoice"
        invoice_path.write_bytes(b"rgb:e2e-invoice")
        artifact = StoredArtifact(
            FrameKind.INVOICE,
            invoice_path,
            invoice_path.stat().st_size,
            "e2e-invoice-hash",
        )
        plan = TransferPlan(
            plan_id="plan-e2e",
            asset_id="rgb:usdt-test",
            recipient_id="recipient-e2e",
            amount=5_000_000,
            balance_before=60_000_000,
            witness_amount_sat=1000,
            fee_rate=2,
            min_confirmations=1,
            expiration_timestamp=1900,
        )
        parsed = ParsedInvoice(
            invoice="rgb:e2e-invoice",
            recipient_id="recipient-e2e",
            asset_id="rgb:usdt-test",
            expiration_timestamp=1900,
            transport_endpoints=(),
            unknown_query_params={},
        )
        self.prepared = InvoiceTransferPlan(parsed, artifact, None, plan)
        consignment_path = directory / f"consignment-{role.value}.rgbc"
        consignment_path.write_bytes(self.payload)
        self.consignment = ConsignmentArtifact(
            "mock-txid",
            4,
            consignment_path,
            len(self.payload),
            "e2e-consignment-hash",
        )
        self.received = ReceivedArtifact(artifact, 0)

    def cents_from_base_units(self, amount: int) -> int:
        return amount // 10_000

    def issue_handcarry_invoice(self, cents: int) -> HandcarryInvoice:
        if self.role is not BillRole.B or cents != 500:
            raise RgbWebError("mock Bill B invoice refused", retryable=False, broadcast=False)
        return HandcarryInvoice(500, "rgb:e2e-invoice", "e2e-invoice-hash", 1900, 4)

    def plan_handcarry(self, cents: int, invoice_text: str) -> InvoiceTransferPlan:
        if self.role is not BillRole.A or cents != 500:
            raise RgbWebError("mock Bill A plan refused", retryable=False, broadcast=False)
        if invoice_text.strip() != "rgb:e2e-invoice":
            raise RgbWebError("paste one invoice line", retryable=True, broadcast=False)
        return self.prepared

    def confirm_handcarry(self, plan_id: str, phrase: str) -> HandcarrySend:
        if phrase != f"CONFIRM {plan_id}":
            raise RgbWebError(
                "confirmation phrase did not match; nothing was sent",
                retryable=True,
                broadcast=False,
            )
        self.confirm_calls += 1
        return HandcarrySend(self.consignment, self.payload)

    def import_handcarry(self, payload: bytes) -> ImportOutcome:
        if payload != self.payload:
            raise RgbWebError("mock consignment did not match", retryable=False, broadcast=False)
        self.imported = True
        return ImportOutcome(self.received, {4: "waiting_confirmations"})

    def refresh_settlement(self) -> tuple[int, dict[int, str]]:
        if self.role is BillRole.B and self.imported and self.settle:
            return 500, {4: "settled"}
        if self.role is BillRole.B:
            return 0, {4: "waiting_confirmations"}
        return 5500, {4: "waiting_counterparty"}


def probe_mutinynet(timeout: float = 3.0) -> bool:
    try:
        with socket.create_connection(("mutinynet.com", 443), timeout):
            return True
    except OSError:
        return False


def _reset(role: str, cents: int) -> None:
    with _state_lock:
        _state.update(
            {
                "role": role,
                "identity": f"bill-{role.lower()}-mock",
                "status": "idle",
                "cents": cents,
                "pending": None,
                "receipts": [],
                "recovery": None,
                "settlement": "not-broadcast",
                "asset_id": "rgb:usdt-test",
                "asset_precision": 6,
                "expected_receive_cents": None,
                "expected_expiration": None,
                "checks": [],
                "pending_cents": 0,
                "check_state": None,
            }
        )


def _snapshot() -> dict:
    with _state_lock:
        return json.loads(json.dumps(_state))


def _restore(saved: dict) -> None:
    with _state_lock:
        _state.clear()
        _state.update(saved)


def run_mock(note: str) -> int:
    """Drive the real handlers. The mock wallet never broadcasts."""

    os.environ.pop("CHECK_LEDGER_PATH", None)
    os.environ.pop("RGB_DATA_DIR", None)
    directory = Path(os.environ.get("TMPDIR", "/tmp")) / "forku-e2e-mock"
    directory.mkdir(parents=True, exist_ok=True)
    desk_a = MockDesk(BillRole.A, directory)
    desk_b = MockDesk(BillRole.B, directory)

    _reset("B", 0)
    invoice = handle_noradio_invoice(500, desk_b)
    if not invoice["ok"] or invoice["handcarry"]["transport_endpoints"] != []:
        print("E2E_ERROR=invoice was not a hand-carry with empty transport endpoints")
        return 1
    saved_b = _snapshot()
    invoice_text = invoice["handcarry"]["invoice"]

    _reset("A", 6000)
    planned = handle_noradio_plan(500, invoice_text, desk_a)
    pending = planned["pending"]
    if "confirmation_phrase" in pending:
        print("E2E_ERROR=plan echoed a confirmation phrase")
        return 1
    phrase = "CONFIRM " + pending["id"]
    wrong = handle_confirm(pending["id"], "CONFIRM wrong", desk_a, handcarry=True)
    if wrong.get("ok") or desk_a.confirm_calls != 0 or "handcarry" in wrong:
        print("E2E_ERROR=wrong phrase exported or broadcast")
        return 1
    if _state["cents"] != 6000:
        print("E2E_ERROR=wrong phrase changed spendable")
        return 1

    sent = handle_confirm(pending["id"], phrase, desk_a, handcarry=True)
    if not sent.get("ok") or not sent.get("handcarry", {}).get("body"):
        print("E2E_ERROR=confirm did not return a consignment to copy")
        return 1
    if sent["bill"]["cents"] != 5500 or sent["bill"]["pending_cents"] != 0:
        print("E2E_ERROR=sender spendable was not reduced only by the send")
        return 1
    if sent["handcarry"]["note"] != "I did not send this to the other desk. Copy it yourself.":
        print("E2E_ERROR=hand-carry note missing")
        return 1
    encoded = sent["handcarry"]["body"]

    _restore(saved_b)
    accepted = handle_noradio_import(encoded, desk_b)
    bill = accepted["bill"]
    incoming = next(check for check in bill["checks"] if check["direction"] != "out")
    if (
        not accepted["ok"]
        or bill["cents"] != 0
        or bill["pending_cents"] != 500
        or incoming["label"] != ACCEPTED_LABEL
        or incoming["counts_toward_spendable"]
    ):
        print("E2E_ERROR=accept credited spendable or hid the pending label")
        return 1

    desk_b.settle = True
    settled = handle_refresh(desk_b)
    settled_bill = settled["bill"]
    if (
        not settled["ok"]
        or settled_bill["check_state"] != "SETTLED"
        or settled_bill["cents"] != 500
        or settled_bill["pending_cents"] != 0
    ):
        print("E2E_ERROR=mock settle did not come from the wallet refresh")
        return 1

    print("E2E_NETWORK=mock")
    print(f"E2E_NOTE={note}")
    print("mainnet=false")
    print("spendable_unchanged=true")
    print(f"accept_label={ACCEPTED_LABEL}")
    print("accept_spendable_cents=0")
    print("accept_pending_cents=500")
    print("settle_state=SETTLED")
    print("settle_spendable_cents=500")
    print("coins_moved=0")
    return 0


def _request(method: str, url: str, payload: dict | None = None, timeout: float = 60) -> tuple[int, dict]:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        parsed = json.loads(body) if body else {"ok": False, "error": exc.reason}
        return exc.code, parsed


def _health_ok(health: dict, which: str) -> str | None:
    if health.get("mainnet") is not False or health.get("network") != "mutinynet":
        return f"{which} is not a Mutinynet test dock"
    if health.get("coins") not in (None, "mutinynet-test-only"):
        return f"{which} did not say mutinynet-test-only"
    if health.get("ok") is not True or health.get("wallet_open") is not True:
        return f"{which} wallet is not open"
    return None


def run_live(url_a: str, url_b: str) -> int:
    """Opt-in path. This broadcasts on the docks those URLs already point at."""

    url_a = url_a.rstrip("/")
    url_b = url_b.rstrip("/")
    _, health_a = _request("GET", url_a + "/api/health", timeout=10)
    _, health_b = _request("GET", url_b + "/api/health", timeout=10)
    for which, health in (("E2E_URL_A", health_a), ("E2E_URL_B", health_b)):
        problem = _health_ok(health, which)
        if problem:
            print("E2E_NETWORK=refused")
            print(f"E2E_NOTE={problem}")
            print("mainnet=false")
            print("coins_moved=0")
            return 2

    _status, invoice = _request("POST", url_b + "/api/noradio/invoice", {"cents": 500})
    if not invoice.get("ok"):
        print("E2E_NETWORK=mutinynet")
        print("E2E_NOTE=Bill B did not create an invoice")
        print("coins_moved=0")
        return 1
    text = invoice["handcarry"]["invoice"]
    _status, planned = _request(
        "POST",
        url_a + "/api/noradio/plan",
        {"cents": 500, "invoice": text},
    )
    pending = planned.get("pending") or {}
    if not planned.get("ok") or "confirmation_phrase" in pending:
        print("E2E_NETWORK=mutinynet")
        print("E2E_NOTE=Bill A did not plan, or the plan echoed a phrase")
        print("coins_moved=0")
        return 1
    phrase = "CONFIRM " + str(pending["id"])
    _status, wrong = _request(
        "POST",
        url_a + "/api/confirm",
        {"id": pending["id"], "phrase": "CONFIRM wrong", "handcarry": True},
    )
    if wrong.get("ok") or wrong.get("handcarry"):
        print("E2E_NETWORK=mutinynet")
        print("E2E_NOTE=wrong phrase was accepted; stop and inspect the wallet")
        print("coins_moved=unknown")
        return 1
    _status, sent = _request(
        "POST",
        url_a + "/api/confirm",
        {"id": pending["id"], "phrase": phrase, "handcarry": True},
    )
    carried = sent.get("handcarry") or {}
    if not sent.get("ok") or not carried.get("body"):
        print("E2E_NETWORK=mutinynet")
        print("E2E_NOTE=confirm did not return a consignment; inspect Bill A before retrying")
        print("coins_moved=unknown")
        return 1
    _status, accepted = _request(
        "POST",
        url_b + "/api/noradio/import",
        {"consignment_b64": carried["body"]},
    )
    if not accepted.get("ok"):
        print("E2E_NETWORK=mutinynet")
        print("E2E_NOTE=Bill B did not import; the send may already be broadcast")
        print("coins_moved=test-coins-broadcast-import-failed")
        return 1

    settle_state = accepted["bill"].get("check_state")
    for _ in range(6):
        if settle_state == "SETTLED":
            break
        time.sleep(10)
        _status, refreshed = _request("POST", url_b + "/api/rgb/refresh", {})
        if refreshed.get("ok"):
            settle_state = refreshed["bill"].get("check_state")
    print("E2E_NETWORK=mutinynet")
    print("E2E_NOTE=live docks; health does not probe the indexer")
    print("mainnet=false")
    print(f"accept_label={ACCEPTED_LABEL}")
    print(f"settle_state={settle_state}")
    print("coins_moved=mutinynet-test-coins")
    if settle_state != "SETTLED":
        print("E2E_SETTLED=waiting")
        return 3
    print("E2E_SETTLED=true")
    return 0


def main() -> int:
    force_mock = os.environ.get("E2E_FORCE_MOCK") == "1"
    live = os.environ.get("E2E_LIVE") == "1"
    url_a = os.environ.get("E2E_URL_A", "").strip()
    url_b = os.environ.get("E2E_URL_B", "").strip()
    if force_mock:
        print("MUTINYNET_TCP=not-probed")
        return run_mock("labeled mock; E2E_FORCE_MOCK=1; no Mutinynet coins moved")
    if live and (not url_a or not url_b):
        print("MUTINYNET_TCP=not-probed")
        print("E2E_NETWORK=refused")
        print("E2E_NOTE=E2E_LIVE=1 requires E2E_URL_A and E2E_URL_B; nothing was sent")
        print("mainnet=false")
        print("coins_moved=0")
        return 2
    reachable = probe_mutinynet()
    print("MUTINYNET_TCP=" + ("reachable" if reachable else "unreachable"))
    if live:
        return run_live(url_a, url_b)
    if reachable:
        note = (
            "labeled mock; Mutinynet TCP reachable; live spend not requested; "
            "no Mutinynet coins moved"
        )
    else:
        note = "labeled mock; Mutinynet TCP unreachable; no Mutinynet coins moved"
    return run_mock(note)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print("E2E_NETWORK=error")
        print(f"E2E_NOTE={type(exc).__name__}: {exc}")
        print("coins_moved=0")
        raise SystemExit(1) from exc
