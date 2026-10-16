"""Five-state check status. Pending money is never spendable.

The labels match the FORKU2BTC desk. rgb-lib ``failed`` is a failure, not a
wait. Restart re-reads the stored checks and does not promote them to settled.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Mapping

ISSUED = "ISSUED"
ACCEPTED = "ACCEPTED"
SETTLING = "SETTLING"
SETTLED = "SETTLED"
FAILED = "FAILED"
EXPIRED = "EXPIRED"
CONFLICT = "CONFLICT"

STATES = (ISSUED, ACCEPTED, SETTLING, SETTLED, FAILED, EXPIRED, CONFLICT)
# A failure must beat a wait. Settled must not hide anything still open.
PRIORITY = (CONFLICT, FAILED, EXPIRED, SETTLING, ACCEPTED, ISSUED, SETTLED)
PENDING_STATES = frozenset({ACCEPTED, SETTLING})
FAILURE_STATES = frozenset({FAILED, EXPIRED, CONFLICT})

ACCEPTED_LABEL = "ACCEPTED - NOT YET SETTLED ON-CHAIN"
ISSUED_DETAIL = "Created. Not accepted."
ACCEPT_BANNER = (
    "Accepted – not yet settled on-chain. "
    "The sender could still cancel until it settles."
)
NOT_A_GUARANTEE = (
    "I can't promise that cancelling costs the sender more than creating "
    "the check. That property does not hold in this build."
)
FUNDS_NOT_LOCKED = (
    "This check is only as good as what we can prove. Funds are NOT locked yet."
)
FUNDS_UNPROVEN = "Offline I cannot prove the funds exist or are unspent."
CANCEL_COSTS_MORE_HOLDS = False

_CONFIRMATIONS = re.compile(r"(\d+)\s*/\s*(\d+)")


def normalize_status(value: object) -> str:
    text = str(value or "").strip().lower().replace("-", " ").replace("_", " ")
    return " ".join(text.split())


def _compact(value: object) -> str:
    text = _CONFIRMATIONS.sub(" ", normalize_status(value))
    return "".join(text.split())


def parse_confirmations(value: object) -> tuple[int, int] | None:
    match = _CONFIRMATIONS.search(str(value or ""))
    if match is None:
        return None
    seen = int(match.group(1))
    required = int(match.group(2))
    if required < 1:
        return None
    return seen, required


def map_rgb_status(
    raw: object,
    *,
    confirmations: int | None = None,
    required: int = 1,
    failure: object | None = None,
) -> str | None:
    """Map one rgb-lib (or desk) status onto the five-state machine.

    ``waiting_confirmations`` with no confirmations is ACCEPTED, not settled
    and not a failure. ``failed`` is never a waiting state. Settled requires
    the settled status and, when a count is present, enough confirmations.
    """

    compact = _compact(raw)
    failure_text = normalize_status(failure)
    failure_compact = failure_text.replace(" ", "")
    blob = f"{compact} {failure_compact}"
    parsed = parse_confirmations(raw)
    if parsed is not None:
        confirmations, required = parsed
    required = required if required >= 1 else 1

    if any(token in blob for token in ("doublespent", "doublespend", "conflict")):
        return CONFLICT
    if "expir" in blob:
        return EXPIRED
    if "fail" in compact or "fail" in failure_compact:
        return FAILED
    if compact in {"settled"}:
        if confirmations is None or confirmations >= required:
            return SETTLED
        return SETTLING
    if compact in {"waitingconfirmations", "settling", "seen"}:
        seen = 0 if confirmations is None else confirmations
        if seen > 0:
            return SETTLING
        return ACCEPTED
    if compact in {
        "waitingcounterparty",
        "issued",
        "broadcast",
        "notbroadcast",
        "created",
    }:
        return ISSUED
    if compact in {"unknown", ""}:
        return None
    return None


def detail_for(
    state: str | None,
    *,
    confirmations: int = 0,
    required: int = 1,
) -> str:
    if state == ISSUED:
        return ISSUED_DETAIL
    if state == ACCEPTED:
        return ACCEPTED_LABEL
    if state == SETTLING:
        seen = max(0, int(confirmations))
        need = required if required >= 1 else 1
        return f"Seen on-chain, {seen}/{need} confirmations"
    if state == SETTLED:
        return "SETTLED"
    if state == FAILED:
        return "FAILED"
    if state == EXPIRED:
        return "EXPIRED"
    if state == CONFLICT:
        return "CONFLICT"
    return ""


def settlement_key(state: str | None) -> str:
    return {
        ISSUED: "issued",
        ACCEPTED: "accepted",
        SETTLING: "settling",
        SETTLED: "settled",
        FAILED: "failed",
        EXPIRED: "expired",
        CONFLICT: "conflict",
    }.get(state or "", "not-broadcast")


def dominant_state(states: list[str | None]) -> str | None:
    present = {state for state in states if state}
    for state in PRIORITY:
        if state in present:
            return state
    return None


def counts_toward_spendable(state: str | None) -> bool:
    """No check record is added into the wallet figure by this desk."""

    return False if state in STATES or state is None else False


def receive_spendable(spendable_cents: int, amount_cents: int, state: str) -> int:
    """Import never credits the desk. The wallet figure is the only balance.

    ``amount_cents`` is part of the signature so callers cannot quietly add it.
    """

    del amount_cents, state
    return int(spendable_cents)


def pending_amount_cents(checks: list[Mapping[str, object]]) -> int:
    total = 0
    for check in checks:
        if check.get("direction", "in") != "in":
            continue
        if check.get("state") not in PENDING_STATES:
            continue
        total += int(check.get("amount_cents") or 0)
    return total


def balance_view(
    wallet_spendable_cents: int,
    checks: list[Mapping[str, object]],
) -> dict[str, int]:
    """Spendable is the wallet number. Pending is a separate pile."""

    return {
        "spendable_cents": int(wallet_spendable_cents),
        "pending_cents": pending_amount_cents(checks),
    }


def recipient_fingerprint(recipient_id: str) -> str:
    if not recipient_id:
        return ""
    digest = hashlib.sha256(recipient_id.encode("utf-8")).hexdigest()
    return f"{digest[:8]}…{digest[-8:]}"


def _mark(ok: bool, detail: str) -> dict[str, object]:
    return {"ok": bool(ok), "mark": "✓" if ok else "✗", "detail": detail}


def offline_accept_report(
    *,
    now: int,
    expiration: int | None,
    payee_id: str | None,
    my_id: str | None,
    consignment_parsed: bool | None,
    signature_valid: bool | None,
) -> dict[str, object]:
    """Local checks only. Funds and signatures are not proven on this desk."""

    if expiration is None:
        not_expired = _mark(False, "No expiry was given, so I will not call it valid.")
    elif int(expiration) <= int(now):
        not_expired = _mark(False, "This check is past its expiry.")
    else:
        not_expired = _mark(True, "Still inside the expiry.")

    if payee_id and my_id and payee_id == my_id:
        payee = _mark(True, "Payee matches me.")
    elif not payee_id or not my_id:
        payee = _mark(
            False,
            "I don't have both ids, so I can't show that the payee is me.",
        )
    else:
        payee = _mark(False, "Payee does not match me.")

    if consignment_parsed is True:
        parsed = _mark(True, "Consignment parsed locally.")
    else:
        parsed = _mark(False, "I cannot prove the consignment parses offline.")

    if signature_valid is True:
        signature = _mark(True, "Signature checked out locally.")
    else:
        signature = _mark(False, "I cannot prove the signature on this desk.")

    return {
        "signature_valid": signature,
        "not_expired": not_expired,
        "payee_is_me": payee,
        "consignment_parses": parsed,
        "funds_exist": _mark(False, "Offline I cannot prove the funds exist."),
        "unspent": _mark(False, "Offline I cannot prove the funds are unspent."),
        "funds_line": FUNDS_UNPROVEN,
    }


def build_check(
    *,
    check_id: str,
    amount_cents: int,
    raw_status: object,
    direction: str = "in",
    confirmations: int | None = None,
    required: int = 1,
    failure: object | None = None,
    **extra: object,
) -> dict[str, object]:
    parsed = parse_confirmations(raw_status)
    if parsed is not None:
        confirmations, required = parsed
    state = map_rgb_status(
        raw_status,
        confirmations=confirmations,
        required=required,
        failure=failure,
    )
    if state is None:
        state = ISSUED if direction == "out" else ACCEPTED
    seen = 0 if confirmations is None else int(confirmations)
    if state == SETTLED:
        seen = required if required >= 1 else 1
    check: dict[str, object] = {
        "check_id": str(check_id),
        "amount_cents": int(amount_cents),
        "direction": direction if direction in {"in", "out"} else "in",
        "state": state,
        "label": detail_for(state, confirmations=seen, required=required),
        "confirmations": seen,
        "required_confirmations": required if required >= 1 else 1,
        "counts_toward_spendable": False,
        "rgb_status": str(raw_status),
        "hidden_fees_sats": 0,
    }
    if failure:
        check["failure"] = str(failure)
    for key, value in extra.items():
        if value is not None:
            check[key] = value
    return check


def apply_observed(
    checks: list[Mapping[str, object]],
    updated: Mapping[object, object],
    *,
    failures: Mapping[object, object] | None = None,
) -> list[dict[str, object]]:
    """Update stored checks from a refresh. Unknown ids are left alone.

    A status that does not map (empty, unknown) does not demote a stored check
    into a waiting bucket.
    """

    cloned = [dict(check) for check in checks]
    by_id = {str(check.get("check_id")): check for check in cloned}
    failure_map = failures or {}
    for key, raw in updated.items():
        check = by_id.get(str(key))
        if check is None:
            continue
        required = int(check.get("required_confirmations") or 1)
        confirmations = check.get("confirmations")
        seen = int(confirmations) if isinstance(confirmations, int) else None
        failure = failure_map.get(key, failure_map.get(str(key), check.get("failure")))
        state = map_rgb_status(
            raw,
            confirmations=seen,
            required=required,
            failure=failure,
        )
        parsed = parse_confirmations(raw)
        if parsed is not None:
            seen, required = parsed
            state = map_rgb_status(
                raw,
                confirmations=seen,
                required=required,
                failure=failure,
            )
        if state is None:
            continue
        if state == SETTLED:
            seen = required
        check["state"] = state
        check["confirmations"] = 0 if seen is None else int(seen)
        check["required_confirmations"] = required
        check["label"] = detail_for(
            state,
            confirmations=int(check["confirmations"]),
            required=required,
        )
        check["counts_toward_spendable"] = False
        check["rgb_status"] = str(raw)
        if failure:
            check["failure"] = str(failure)
    return cloned


def rederive(
    checks: list[Mapping[str, object]],
    observed: Mapping[object, object] | None = None,
    *,
    now: int | None = None,
    failures: Mapping[object, object] | None = None,
) -> list[dict[str, object]]:
    """Restore checks after a restart.

    Pending stays pending when nothing new was observed. Nothing is promoted
    to SETTLED unless this call was given a settled observation. An issued
    check past ``expires`` becomes EXPIRED when ``now`` is provided.
    """

    restored = apply_observed(checks, observed or {}, failures=failures)
    if now is None:
        return restored
    for check in restored:
        expires = check.get("expires")
        if check.get("state") == ISSUED and isinstance(expires, int) and expires <= now:
            check["state"] = EXPIRED
            check["label"] = detail_for(EXPIRED)
            check["counts_toward_spendable"] = False
    return restored


def desk_after_restart(
    spendable_cents: int,
    stored: list[Mapping[str, object]],
    *,
    now: int | None = None,
    observed: Mapping[object, object] | None = None,
) -> dict[str, object]:
    checks = rederive(stored, observed, now=now)
    view = balance_view(spendable_cents, checks)
    state = dominant_state([str(check.get("state")) for check in checks])
    if state is None:
        settlement = "settled"
        status = "idle"
    else:
        settlement = settlement_key(state)
        status = settlement
    return {
        "spendable_cents": view["spendable_cents"],
        "pending_cents": view["pending_cents"],
        "checks": checks,
        "check_state": state,
        "settlement": settlement,
        "status": status,
    }


def observed_desk_state(updated: Mapping[object, object]) -> str | None:
    return dominant_state([map_rgb_status(value) for value in updated.values()])


def primary_observation(
    updated: Mapping[object, object],
) -> tuple[str, object, str | None]:
    """Pick the check id whose rgb status dominates the set."""

    pairs = [
        (str(key), value, map_rgb_status(value)) for key, value in updated.items()
    ]
    if not pairs:
        return "import", "waiting_confirmations", ACCEPTED
    state = dominant_state([item[2] for item in pairs])
    for key, value, mapped in pairs:
        if mapped == state:
            return key, value, state
    key, value, mapped = pairs[0]
    return key, value, mapped


def save_checks(path: Path, checks: list[Mapping[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps({"checks": [dict(check) for check in checks]}, indent=2)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(payload, encoding="utf-8")
    os.replace(temporary, path)


def load_checks(path: Path | None) -> list[dict[str, object]]:
    if path is None or not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    raw = data.get("checks") if isinstance(data, dict) else data
    if not isinstance(raw, list):
        return []
    return [dict(item) for item in raw if isinstance(item, dict)]
