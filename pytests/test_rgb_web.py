import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from dock.chunk_protocol import FrameKind
from web.rgb.adapter import ConfirmationRequired, ConsignmentArtifact, TransferPlan
from web.rgb.backend import ParsedInvoice, ReceiveIntent
from web.rgb.config import BillRole
from web.rgb.tap_flow import (
    InvoiceTransferPlan,
    ReceivedArtifact,
    StagedArtifact,
    StoredArtifact,
)
from web.rgb_web import RgbWebError, RgbWebService


class FakeAdapter:
    def __init__(self, role: BillRole) -> None:
        self.settings = SimpleNamespace(role=role)
        self.confirmed = []
        self.closed = False

    def spendable_balance(self, _asset_id):
        return 60_000_000

    def confirm_transfer(self, plan_id):
        self.confirmed.append(plan_id)

    def close(self):
        self.closed = True

    def refresh_transfers(self):
        return {7: "settled"}


class RecoveryFlow:
    def __init__(self, tmp_path: Path, role: BillRole) -> None:
        self.adapter = FakeAdapter(role)
        self.create_invoice_calls = 0
        self.stage_artifact_calls = 0
        self.execute_calls = 0
        self.stage_consignment_calls = 0
        self.receive_calls = 0
        self.import_calls = 0
        invoice_path = tmp_path / "invoice.rgb-invoice"
        invoice_path.write_bytes(b"invoice")
        self.invoice = StoredArtifact(
            FrameKind.INVOICE,
            invoice_path,
            len(b"invoice"),
            "invoice-hash",
        )
        consignment_path = tmp_path / "consignment.rgbc"
        consignment_path.write_bytes(b"consignment")
        self.consignment = ConsignmentArtifact(
            "txid",
            7,
            consignment_path,
            len(b"consignment"),
            "consignment-hash",
        )
        self.stored_consignment = StoredArtifact(
            FrameKind.CONSIGNMENT,
            consignment_path,
            len(b"consignment"),
            "consignment-hash",
        )

    def create_invoice_artifact(self, **_kwargs):
        self.create_invoice_calls += 1
        return ReceiveIntent("invoice", "recipient", 1900, 4), self.invoice

    def stage_artifact(self, artifact, denomination_cents=0):
        self.stage_artifact_calls += 1
        if self.stage_artifact_calls == 1:
            raise RuntimeError("BLE unavailable")
        return StagedArtifact(artifact, 0x11111111)

    def execute_confirmed_transfer(self, plan_id):
        assert plan_id == "plan-123"
        self.execute_calls += 1
        return self.consignment

    def stage_consignment(self, _artifact, denomination_cents=0):
        self.stage_consignment_calls += 1
        if self.stage_consignment_calls == 1:
            raise RuntimeError("BLE unavailable")
        return StagedArtifact(self.stored_consignment, 0x22222222)

    def receive_consignment(self):
        self.receive_calls += 1
        return ReceivedArtifact(self.stored_consignment, 0x22222222)

    def import_consignment(self, _received):
        self.import_calls += 1
        if self.import_calls == 1:
            raise RuntimeError("indexer timeout")
        return {4: "waiting_confirmations"}


def test_invoice_stage_retry_reuses_same_native_invoice(tmp_path):
    flow = RecoveryFlow(tmp_path, BillRole.B)
    service = RgbWebService(flow, asset_id="rgb:usdt", asset_precision=6)

    first = service.stage_invoice(500)
    second = service.stage_invoice(500)

    assert first.staged is None
    assert second.staged is not None
    assert flow.create_invoice_calls == 1
    assert flow.stage_artifact_calls == 2
    assert first.artifact.path == second.artifact.path


def test_post_broadcast_retry_stages_same_consignment_without_resend(tmp_path):
    flow = RecoveryFlow(tmp_path, BillRole.A)
    service = RgbWebService(flow, asset_id="rgb:usdt", asset_precision=6)
    service._confirmation_phrases["plan-123"] = "CONFIRM plan-123"

    first = service.confirm_and_stage("plan-123", "CONFIRM plan-123")
    second = service.retry_consignment_stage()

    assert first.staged is None
    assert second.staged is not None
    assert first.consignment.path == second.consignment.path
    assert flow.execute_calls == 1
    assert flow.stage_consignment_calls == 2
    assert flow.adapter.confirmed == ["plan-123"]


def test_import_retry_reuses_received_artifact_without_second_ble_receive(tmp_path):
    flow = RecoveryFlow(tmp_path, BillRole.B)
    service = RgbWebService(flow, asset_id="rgb:usdt", asset_precision=6)

    first = service.receive_and_import()
    second = service.receive_and_import()

    assert first.updated_transfers is None
    assert second.updated_transfers == {4: "waiting_confirmations"}
    assert first.received.artifact.path == second.received.artifact.path
    assert flow.receive_calls == 1
    assert flow.import_calls == 2


def test_web_amount_conversion_uses_configured_asset_precision(tmp_path):
    flow = RecoveryFlow(tmp_path, BillRole.A)
    service = RgbWebService(flow, asset_id="rgb:usdt", asset_precision=6)

    assert service.amount_base_units(500) == 5_000_000
    assert service.cents_from_base_units(60_000_000) == 6000
    assert service.spendable_cents() == 6000
    assert service.refresh_settlement() == (6000, {7: "settled"})


def test_confirmation_secret_is_not_the_plan_id(tmp_path):
    flow = RecoveryFlow(tmp_path, BillRole.A)
    plan = TransferPlan(
        "plan-123",
        "rgb:usdt",
        "recipient",
        5_000_000,
        60_000_000,
        1000,
        2,
        1,
        1900,
    )
    parsed = ParsedInvoice("invoice", "recipient", "rgb:usdt", 1900, (), {})

    def receive_and_plan_invoice(**_kwargs):
        return InvoiceTransferPlan(parsed, flow.invoice, None, plan)

    flow.receive_and_plan_invoice = receive_and_plan_invoice
    service = RgbWebService(flow, asset_id="rgb:usdt", asset_precision=6)

    prepared = service.plan_transfer(500)

    assert prepared.confirmation_phrase.startswith("CONFIRM ")
    assert "plan-123" not in prepared.confirmation_phrase
    with pytest.raises(RgbWebError, match="nothing was sent") as caught:
        service.confirm_and_stage("plan-123", "CONFIRM plan-123")
    assert caught.value.retryable is True
    assert caught.value.broadcast is False
    assert flow.execute_calls == 0

    outcome = service.confirm_and_stage("plan-123", prepared.confirmation_phrase)

    assert outcome.consignment.txid == "txid"
    assert flow.execute_calls == 1


def test_expired_plan_is_retryable_and_not_an_unknown_broadcast(tmp_path):
    flow = RecoveryFlow(tmp_path, BillRole.A)

    def confirm_transfer(_plan_id):
        raise ConfirmationRequired("transfer plan expired before confirmation")

    flow.adapter.confirm_transfer = confirm_transfer
    service = RgbWebService(flow, asset_id="rgb:usdt", asset_precision=6)
    service._confirmation_phrases["plan-123"] = "CONFIRM plan-123"

    with pytest.raises(RgbWebError, match="not broadcast") as caught:
        service.confirm_and_stage("plan-123", "CONFIRM plan-123")

    assert caught.value.retryable is True
    assert caught.value.broadcast is False
    assert caught.value.clear_pending is True
    assert flow.execute_calls == 0


def test_ambiguous_send_stays_unretryable(tmp_path):
    flow = RecoveryFlow(tmp_path, BillRole.A)

    def confirm_transfer(_plan_id):
        raise RuntimeError("socket reset during send")

    flow.adapter.confirm_transfer = confirm_transfer
    service = RgbWebService(flow, asset_id="rgb:usdt", asset_precision=6)
    service._confirmation_phrases["plan-123"] = "CONFIRM plan-123"

    with pytest.raises(RgbWebError, match="unknown broadcast outcome") as caught:
        service.confirm_and_stage("plan-123", "CONFIRM plan-123")

    assert caught.value.retryable is False
    assert caught.value.broadcast is None


def test_journal_restores_broadcast_consignment_for_stage_retry(tmp_path):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    flow = RecoveryFlow(tmp_path, BillRole.A)
    digest = hashlib.sha256(b"consignment").hexdigest()
    flow.consignment = ConsignmentArtifact(
        "txid",
        7,
        flow.consignment.path,
        len(b"consignment"),
        digest,
    )
    flow.adapter.settings = SimpleNamespace(role=BillRole.A, inbox_dir=inbox)
    service = RgbWebService(flow, asset_id="rgb:usdt", asset_precision=6)
    service._confirmation_phrases["plan-123"] = "CONFIRM plan-123"

    first = service.confirm_and_stage("plan-123", "CONFIRM plan-123")

    journal = inbox / "pending-consignment.json"
    assert first.staged is None
    assert journal.exists()
    assert journal.stat().st_mode & 0o777 == 0o600
    assert flow.execute_calls == 1

    restored = RgbWebService(flow, asset_id="rgb:usdt", asset_precision=6)
    pending = restored.pending_outbound()
    assert pending is not None
    assert pending[0] == 500
    assert pending[1].path == first.consignment.path
    assert pending[1].sha256 == first.consignment.sha256

    second = restored.retry_consignment_stage()

    assert second.staged is not None
    assert flow.execute_calls == 1
    assert not journal.exists()
