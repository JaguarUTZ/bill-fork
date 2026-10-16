"""Status machine: accepted money stays pending and out of spendable."""

from web.check_status import (
    ACCEPTED,
    ACCEPTED_LABEL,
    CONFLICT,
    EXPIRED,
    FAILED,
    ISSUED,
    SETTLING,
    SETTLED,
    balance_view,
    build_check,
    desk_after_restart,
    detail_for,
    load_checks,
    map_rgb_status,
    offline_accept_report,
    pending_amount_cents,
    receive_spendable,
    rederive,
    save_checks,
)


def test_accepted_label_and_spendable_split():
    check = build_check(
        check_id="4",
        amount_cents=500,
        raw_status="waiting_confirmations",
        direction="in",
    )

    assert check["state"] == ACCEPTED
    assert check["label"] == ACCEPTED_LABEL
    assert check["counts_toward_spendable"] is False
    assert receive_spendable(4000, 500, ACCEPTED) == 4000
    view = balance_view(4000, [check])
    assert view["spendable_cents"] == 4000
    assert view["pending_cents"] == 500
    assert view["spendable_cents"] != 4000 + 500


def test_rgb_failed_expired_and_conflict_are_not_waiting():
    assert map_rgb_status("failed") == FAILED
    assert map_rgb_status("Failed") == FAILED
    assert map_rgb_status("waiting_confirmations", failure="expired invoice") == EXPIRED
    assert map_rgb_status("double_spent") == CONFLICT
    assert map_rgb_status("waiting_counterparty", failure="conflict") == CONFLICT
    for raw in ("failed", "expired", "conflict", "double_spent"):
        state = map_rgb_status(raw)
        assert state not in {ACCEPTED, SETTLING, SETTLED, None}
        assert "waiting" not in detail_for(state).lower()


def test_settled_only_after_confirmations_and_settling_shows_the_count():
    assert map_rgb_status("settled", confirmations=0, required=1) == SETTLING
    assert map_rgb_status("settled", confirmations=1, required=1) == SETTLED
    assert map_rgb_status("settled") == SETTLED
    check = build_check(
        check_id="9",
        amount_cents=500,
        raw_status="waiting_confirmations 1/1",
        direction="in",
    )
    assert check["state"] == SETTLING
    assert check["label"] == "Seen on-chain, 1/1 confirmations"
    assert pending_amount_cents([check]) == 500
    assert receive_spendable(4000, 500, SETTLING) == 4000


def test_issued_outgoing_is_not_pending_spendable():
    check = build_check(
        check_id="7",
        amount_cents=500,
        raw_status="waiting_counterparty",
        direction="out",
    )
    assert check["state"] == ISSUED
    assert check["label"] == "Created. Not accepted."
    assert pending_amount_cents([check]) == 0
    assert balance_view(5500, [check])["spendable_cents"] == 5500


def test_restart_keeps_accepted_pending_and_does_not_settle_it(tmp_path):
    stored = [
        build_check(
            check_id="4",
            amount_cents=500,
            raw_status="waiting_confirmations",
            direction="in",
        )
    ]
    path = tmp_path / "check-ledger.json"
    save_checks(path, stored)

    desk = desk_after_restart(4000, load_checks(path))

    assert desk["spendable_cents"] == 4000
    assert desk["pending_cents"] == 500
    assert desk["check_state"] == ACCEPTED
    assert desk["settlement"] == "accepted"
    assert desk["settlement"] != "settled"
    assert desk["checks"][0]["label"] == ACCEPTED_LABEL


def test_restart_applies_observed_failure_without_dropping_other_pending():
    stored = [
        build_check(
            check_id="4",
            amount_cents=500,
            raw_status="waiting_confirmations",
        ),
        build_check(
            check_id="8",
            amount_cents=200,
            raw_status="waiting_confirmations",
        ),
    ]
    restored = rederive(stored, {"4": "failed"})
    desk = desk_after_restart(1000, restored)

    states = {check["check_id"]: check["state"] for check in restored}
    assert states["4"] == FAILED
    assert states["8"] == ACCEPTED
    assert desk["pending_cents"] == 200
    assert desk["spendable_cents"] == 1000
    assert desk["settlement"] == "failed"


def test_issued_check_past_expiry_becomes_expired_on_restart():
    stored = [
        build_check(
            check_id="plan",
            amount_cents=500,
            raw_status="issued",
            direction="out",
            expires=100,
        )
    ]
    restored = rederive(stored, now=101)
    assert restored[0]["state"] == EXPIRED
    assert pending_amount_cents(restored) == 0


def test_offline_report_never_claims_funds():
    report = offline_accept_report(
        now=1_000,
        expiration=2_000,
        payee_id="me",
        my_id="me",
        consignment_parsed=True,
        signature_valid=True,
    )
    assert report["not_expired"]["ok"] is True
    assert report["payee_is_me"]["ok"] is True
    assert report["funds_exist"]["ok"] is False
    assert report["unspent"]["ok"] is False
    assert "cannot prove the funds" in report["funds_line"]

    unknown = offline_accept_report(
        now=1_000,
        expiration=None,
        payee_id=None,
        my_id=None,
        consignment_parsed=None,
        signature_valid=None,
    )
    assert unknown["signature_valid"]["ok"] is False
    assert unknown["consignment_parses"]["ok"] is False
    assert unknown["funds_exist"]["ok"] is False
