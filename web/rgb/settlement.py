"""Map rgb-lib transfer status names onto dock settlement states.

``_enum_name`` lowercases enum names and keeps their underscores, so a waiting
transfer arrives as ``waiting_confirmations``. Failed and expired transfers
must not fall through to that waiting state.
"""

from __future__ import annotations

from collections.abc import Iterable

_WAITING = {
    "waiting_confirmations",
    "waitingconfirmations",
    "waiting_counterparty",
    "waitingcounterparty",
}

_KNOWN = _WAITING | {"settled", "failed", "expired"}


def normalize_status(status: object) -> str:
    return str(status).strip().lower().replace("-", "_")


def classify_transfer_statuses(statuses: Iterable[object]) -> str:
    """Classify a set of transfer statuses.

    An empty set means the wallet reported no outstanding transfer, which the
    startup path treats as settled only after a successful listing. Callers
    that could not list transfers must pass no statuses and then replace this
    result with ``unknown`` themselves. A non-empty set that is not entirely
    ``settled`` never returns ``settled``.
    """
    values = {normalize_status(status) for status in statuses}
    values.discard("")
    if not values:
        return "settled"
    if "failed" in values:
        return "transfer-failed"
    if "expired" in values:
        return "transfer-expired"
    if values <= {"settled"}:
        return "settled"
    if values <= _WAITING or values <= (_WAITING | {"settled"}):
        return "waiting-confirmations"
    if values - _KNOWN:
        return "waiting-confirmations"
    return "waiting-confirmations"


def receive_settlement(kind: str) -> str:
    """Settlement label after a consignment import.

    Waiting and unrecognized non-terminal states stay accepted and unsettled.
    They are not spendable credit.
    """
    if kind == "settled":
        return "settled"
    if kind in {"transfer-failed", "transfer-expired"}:
        return kind
    return "accepted-unsettled"
