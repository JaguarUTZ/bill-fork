from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_dock_and_tap_require_encrypted_gatt():
    header = (ROOT / "include" / "bill_ble_security.h").read_text(encoding="utf-8")
    dock = (ROOT / "lib" / "DockGatt" / "src" / "DockGatt.cpp").read_text(
        encoding="utf-8"
    )
    tap = (ROOT / "lib" / "TapGatt" / "src" / "TapGatt.cpp").read_text(
        encoding="utf-8"
    )

    assert "ESP_LE_AUTH_REQ_SC_BOND" in header
    assert "ESP_IO_CAP_NONE" in header
    assert "no MITM" in header
    assert "configureBillBleSecurity" in dock
    assert "requireEncrypted" in dock
    assert "ESP_GATT_PERM_READ_ENCRYPTED" in dock
    assert "ESP_GATT_PERM_WRITE_ENCRYPTED" in dock
    assert "configureBillBleSecurity" in tap
    assert "ESP_GATT_PERM_READ_ENCRYPTED" in tap
    assert "ESP_GATT_PERM_WRITE_ENCRYPTED" in tap
    assert "no peer authentication" in tap
