"""Static checks for the Forkashi desk skin. No wallet and no hardware."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "web" / "static"

HONESTY = (
    "In this test version, the receiving dock still needs internet "
    "to import the check. Later versions aim to let you accept a "
    "check with no internet and settle afterward."
)
PAUSE = "Game paused. Nothing is sent while you read."
CREDIT = (
    "Based on RGB cash bill by Edwin Kestler "
    "(github.com/EdwinKestler/bill). Forkashi skin by JaguarUTZ."
)
BANNED = (
    "Mario",
    "Zelda",
    "Pokemon",
    "Pokémon",
    "verified offline",
    "offline verification",
)


def _text(name: str) -> str:
    return (STATIC / name).read_text(encoding="utf-8")


def test_app_js_element_ids_exist_in_index() -> None:
    app = _text("app.js")
    html = _text("index.html")
    queried = set(re.findall(r"""getElementById\(\s*["']([^"']+)["']\s*\)""", app))
    assert queried
    missing = sorted(item for item in queried if f'id="{item}"' not in html)
    assert missing == []


def test_typed_confirmation_is_unchanged() -> None:
    app = _text("app.js")
    html = _text("index.html")
    assert 'id="confirmation-phrase"' in html
    assert 'id="approve"' in html
    assert "phrase: confirmationPhrase.value" in app
    assert "/api/confirm" in app
    assert "confirmationPhrase.value = pending" not in app


def test_skin_copy_badges_and_credit() -> None:
    copy = _text("copy.js")
    html = _text("index.html")
    skin = _text("skin.js")
    for line in (
        PAUSE,
        HONESTY,
        "Accepted — not yet settled on-chain",
        "Nothing sent yet",
        "Sent. Waiting for the other bill to import it",
        "SETTLED ON-CHAIN. Final.",
        "Needs attention",
        "You have the check; the blockchain has not confirmed it yet.",
    ):
        assert line in copy
    assert PAUSE in html
    assert HONESTY in html
    assert CREDIT in html
    assert 'id="sound-toggle"' in html
    assert 'aria-pressed="false"' in html
    assert "Sound: OFF" in html
    assert "Sound: ON" in skin
    assert "Sound: OFF" in skin
    assert 'settlement === "waiting-import"' in skin
    assert 'settlement === "waiting-confirmations"' in skin
    assert "bill.recovery" in skin


def test_font_license_and_no_audio_files() -> None:
    license_text = (STATIC / "fonts" / "OFL.txt").read_text(encoding="utf-8")
    assert "SIL OPEN FONT LICENSE" in license_text
    assert "Press Start 2P" in license_text
    font = STATIC / "fonts" / "PressStart2P-Regular.ttf"
    assert font.stat().st_size > 1000
    audio = []
    for pattern in ("*.mp3", "*.wav", "*.ogg", "*.m4a", "*.flac"):
        audio.extend(STATIC.rglob(pattern))
    assert audio == []


def test_skin_does_not_use_borrowed_characters() -> None:
    blob = "\n".join(_text(name) for name in ("index.html", "app.css", "app.js", "skin.js", "copy.js"))
    for banned in BANNED:
        assert banned not in blob
