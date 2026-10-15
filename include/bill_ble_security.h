#pragma once

// Just Works bonding for dock and tap GATT.
//
// Encrypted permissions reject unpaired reads and writes. They do not
// authenticate which peer paired: both sides advertise IO capability None and
// onConfirmPIN accepts the request. A nearby device that completes pairing can
// still read and write. Passive sniffing of an unpaired session is what this
// stops. There is no passkey, no numeric comparison, and no proof that the
// invoice on the bill was written by the receiver the sender intends to pay.

#include <Arduino.h>
#include <BLE2902.h>
#include <BLEDevice.h>
#include <BLESecurity.h>

class BillBleSecurityCallbacks : public BLESecurityCallbacks {
 public:
  uint32_t onPassKeyRequest() override { return 0; }

  void onPassKeyNotify(uint32_t) override {}

  bool onConfirmPIN(uint32_t) override { return true; }

  bool onSecurityRequest() override { return true; }

  void onAuthenticationComplete(esp_ble_auth_cmpl_t result) override {
    if (!result.success) {
      Serial.println("bill: BLE pairing failed");
    }
  }
};

inline void configureBillBleSecurity() {
  static bool configured = false;
  if (configured) {
    return;
  }
  configured = true;
  BLEDevice::setEncryptionLevel(ESP_BLE_SEC_ENCRYPT_NO_MITM);
  BLEDevice::setSecurityCallbacks(new BillBleSecurityCallbacks());
  BLESecurity security;
  security.setAuthenticationMode(ESP_LE_AUTH_REQ_SC_BOND);
  security.setCapability(ESP_IO_CAP_NONE);
  security.setInitEncryptionKey(ESP_BLE_ENC_KEY_MASK | ESP_BLE_ID_KEY_MASK);
  security.setRespEncryptionKey(ESP_BLE_ENC_KEY_MASK | ESP_BLE_ID_KEY_MASK);
  Serial.println(
      "bill: GATT requires encryption (Just Works bond, no MITM authentication)");
}

inline void requireEncrypted(BLECharacteristic* characteristic,
                             esp_gatt_perm_t permissions) {
  characteristic->setAccessPermissions(permissions);
}

inline BLE2902* encryptedCccd() {
  auto* descriptor = new BLE2902();
  descriptor->setAccessPermissions(static_cast<esp_gatt_perm_t>(
      ESP_GATT_PERM_READ_ENCRYPTED | ESP_GATT_PERM_WRITE_ENCRYPTED));
  return descriptor;
}
