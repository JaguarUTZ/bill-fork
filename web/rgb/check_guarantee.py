"""What this dock can and cannot promise about cancelling a transfer.

rgb-lib 0.3.0b7 ``Wallet.send`` builds and broadcasts the witness transaction
during the confirmed send. This package has no CLTV or tapscript escrow, no
penalty bond, and no flag that disables replace-by-fee. A conflicting spend of
the same inputs before settlement is therefore not something this software can
price. Mutinynet confirmation is a custom-signet signer, not an economic cost.

The enforceable substitute is an acceptance rule: the receiver's spendable
balance moves only when the wallet reports spendable funds after settlement.
Importing a consignment does not credit a check.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CheckGuarantee:
    """Machine-readable statement included with every send plan."""

    product: str
    cancel_costs_more_than_create: bool
    offline_validation: bool
    witness_amount_sat: int
    fee_rate_sat_vb: int
    min_confirmations: int
    creation_cost: str
    cancel_cost: str
    what_is_enforced: str

    def as_dict(self) -> dict[str, object]:
        return {
            "product": self.product,
            "cancel_costs_more_than_create": self.cancel_costs_more_than_create,
            "offline_validation": self.offline_validation,
            "witness_amount_sat": self.witness_amount_sat,
            "fee_rate_sat_vb": self.fee_rate_sat_vb,
            "min_confirmations": self.min_confirmations,
            "creation_cost": self.creation_cost,
            "cancel_cost": self.cancel_cost,
            "what_is_enforced": self.what_is_enforced,
        }


_PRODUCT = (
    "tap-to-deliver an already-broadcast transfer; "
    "spendable only after the wallet reports settlement"
)

_CREATION_COST = (
    "Creating the transfer broadcasts one Mutinynet transaction. "
    "The sender pays the miner fee at the configured sat/vB rate plus a witness "
    "output of the configured satoshi amount. The witness output reaches the "
    "receiver only if that transaction confirms. This software does not measure "
    "the signed transaction's vsize, so it does not quote a satoshi fee."
)

_CANCEL_COST = (
    "Not enforced. Before settlement, a conflicting spend of the same inputs can "
    "drop the broadcast. This dock does not build that spend. It also cannot make "
    "the conflicting spend cost more than the original broadcast: rgb-lib "
    "0.3.0b7 Wallet.send exposes no CLTV escrow, penalty bond, or RBF-disable "
    "control, and a replacement can omit the witness output. Mutinynet "
    "confirmation is not economic finality."
)

_ENFORCED = (
    "The receiver dock adds nothing to the spendable balance at import time. "
    "Spendable cents come only from the wallet's spendable balance. An imported "
    "transfer that is waiting, failed, or expired is shown separately and is not "
    "spendable. The sender must confirm a per-plan secret before the one broadcast. "
    "After that broadcast, the dock has no cancel action."
)


def describe_guarantee(
    *,
    witness_amount_sat: int,
    fee_rate_sat_vb: int,
    min_confirmations: int,
) -> CheckGuarantee:
    """Return the fixed guarantee. The false flags are intentional."""
    if witness_amount_sat < 1 or fee_rate_sat_vb < 1 or min_confirmations < 1:
        raise ValueError("guarantee inputs must be positive")
    return CheckGuarantee(
        product=_PRODUCT,
        cancel_costs_more_than_create=False,
        offline_validation=False,
        witness_amount_sat=witness_amount_sat,
        fee_rate_sat_vb=fee_rate_sat_vb,
        min_confirmations=min_confirmations,
        creation_cost=_CREATION_COST,
        cancel_cost=_CANCEL_COST,
        what_is_enforced=_ENFORCED,
    )
