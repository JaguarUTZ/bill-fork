"""Static checks for the FORKU2BTC desk. No wallet and no hardware."""

from __future__ import annotations

import re
from pathlib import Path

from web.check_status import (
    ACCEPT_BANNER,
    ACCEPTED_LABEL,
    FUNDS_NOT_LOCKED,
    FUNDS_UNPROVEN,
    ISSUED_DETAIL,
    NOT_A_GUARANTEE,
)

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "web" / "static"

CREDIT = "Built on Edwin Kestler's bill / O2A."
BANNED = (
    "Mario",
    "Zelda",
    "Pokemon",
    "Pokémon",
    "verified offline",
    "offline verification",
    "fonts.googleapis.com",
    "funds are locked yet",
)


def _text(name: str) -> str:
    return (STATIC / name).read_text(encoding="utf-8")


def _blob() -> str:
    return "\n".join(
        _text(name) for name in ("index.html", "app.css", "app.js", "skin.js", "copy.js")
    )


def test_app_js_element_ids_exist_in_index() -> None:
    app = _text("app.js")
    html = _text("index.html")
    queried = set(re.findall(r"""getElementById\(\s*["']([^"']+)["']\s*\)""", app))
    assert queried
    missing = sorted(item for item in queried if f'id="{item}"' not in html)
    assert missing == []


def test_typed_confirmation_is_client_side() -> None:
    app = _text("app.js")
    html = _text("index.html")
    server = (ROOT / "web" / "server.py").read_text(encoding="utf-8")
    assert 'id="confirmation-phrase"' in html
    assert 'id="approve"' in html
    assert "phrase: confirmationPhrase.value" in app
    assert "/api/confirm" in app
    assert "confirmationPhrase.value = pending" not in app
    assert "confirmation_phrase" not in app
    assert 'return "CONFIRM " + pending.id;' in app
    assert "confirmation_phrase" not in server


def test_honest_status_copy_and_credit() -> None:
    blob = _blob()
    html = _text("index.html")
    css = _text("app.css")
    for line in (
        ACCEPTED_LABEL,
        ISSUED_DETAIL,
        ACCEPT_BANNER,
        NOT_A_GUARANTEE,
        FUNDS_NOT_LOCKED,
        FUNDS_UNPROVEN,
        CREDIT,
        "MUTINYNET · TEST ONLY",
        "Hidden fees",
        "0 sats",
        "Create check",
        "Receive / accept",
        "Settle later",
        "does not hold",
        "Backend offline. I have not reached the dock. Nothing was sent.",
        "I did not send this to the other desk. Copy it yourself.",
        "Mutinynet test coins only",
        "Plan from pasted invoice",
        "Accept pasted consignment",
    ):
        assert line in blob
    online = css.split('#backend-state[data-state="online"]', 1)[1].split("}", 1)[0]
    assert "var(--cyan)" in online
    assert "var(--green)" not in online
    assert ACCEPTED_LABEL in html
    assert CREDIT in html
    assert "Ask Edwin before redistributing" in html
    assert "--yellow: #ffe600" in css
    assert "--green: #39ff88" in css
    assert "--btc: #f7931a" in css
    assert "--bg: #050505" in css
    assert "--ink: #f4efe6" in css
    accepted = css.split('[data-state="ACCEPTED"]', 1)[1].split("}", 1)[0]
    settled = css.split('[data-state="SETTLED"]', 1)[1].split("}", 1)[0]
    assert "var(--yellow)" in accepted
    assert "var(--green)" not in accepted
    assert "var(--green)" in settled
    assert "pending_cents" in _text("app.js")
    assert "dataset.pending" in _text("app.js")
    assert 'data-pending="no"' in html


def test_fonts_are_local_ofl_files() -> None:
    css = _text("app.css")
    assert "fonts.googleapis.com" not in css
    for name in ("Anton", "Space Mono", "Inter"):
        assert name in css
    fonts = STATIC / "fonts"
    for filename in (
        "Anton-Regular.woff2",
        "SpaceMono-Regular.woff2",
        "SpaceMono-Bold.woff2",
        "Inter-Regular.woff2",
        "Inter-SemiBold.woff2",
        "Inter-ExtraBold.woff2",
    ):
        font = fonts / filename
        assert font.stat().st_size > 1000
    for license_name in ("OFL-Anton.txt", "OFL-SpaceMono.txt", "OFL-Inter.txt"):
        text = (fonts / license_name).read_text(encoding="utf-8")
        assert "SIL OPEN FONT LICENSE" in text
    audio = []
    for pattern in ("*.mp3", "*.wav", "*.ogg", "*.m4a", "*.flac"):
        audio.extend(STATIC.rglob(pattern))
    assert audio == []


def test_skin_does_not_claim_cancel_costs_more_or_borrowed_characters() -> None:
    blob = _blob()
    for banned in BANNED:
        assert banned not in blob
    assert "costs the sender more than creating the check" in blob
    assert blob.count("does not hold") >= 1
