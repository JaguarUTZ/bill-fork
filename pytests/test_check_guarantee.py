from web.rgb.check_guarantee import describe_guarantee
from web.rgb.settlement import classify_transfer_statuses, receive_settlement


def test_guarantee_does_not_claim_a_check():
    guarantee = describe_guarantee(
        witness_amount_sat=1000,
        fee_rate_sat_vb=2,
        min_confirmations=1,
    )

    assert guarantee.cancel_costs_more_than_create is False
    assert guarantee.offline_validation is False
    assert "not an offline check" in guarantee.product or "already-broadcast" in guarantee.product
    payload = guarantee.as_dict()
    assert payload["cancel_costs_more_than_create"] is False
    assert "CLTV" in payload["cancel_cost"]
    assert "spendable balance" in payload["what_is_enforced"]


def test_failed_and_expired_are_not_waiting_or_settled():
    assert classify_transfer_statuses(["failed"]) == "transfer-failed"
    assert classify_transfer_statuses(["FAILED"]) == "transfer-failed"
    assert classify_transfer_statuses(["expired", "settled"]) == "transfer-expired"
    assert (
        classify_transfer_statuses(["waiting_confirmations"])
        == "waiting-confirmations"
    )
    assert classify_transfer_statuses(["settled", "waiting_confirmations"]) == (
        "waiting-confirmations"
    )
    assert classify_transfer_statuses(["settled"]) == "settled"
    assert classify_transfer_statuses([]) == "settled"
    assert receive_settlement("waiting-confirmations") == "accepted-unsettled"
    assert receive_settlement("transfer-failed") == "transfer-failed"
    assert receive_settlement("settled") == "settled"
