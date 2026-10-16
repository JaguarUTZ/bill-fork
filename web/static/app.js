const logEl = document.getElementById("log");
const form = document.getElementById("form");
const text = document.getElementById("text");
const dialog = document.getElementById("confirm");
const confirmNote = document.getElementById("confirm-note");
const confirmPlan = document.getElementById("confirm-plan");
const confirmationPhrase = document.getElementById("confirmation-phrase");
const confirmForm = document.getElementById("confirm-form");
const scanDevice = document.getElementById("scan-device");
const connectDevice = document.getElementById("connect-device");
const registerDevice = document.getElementById("register-device");
const deviceList = document.getElementById("device-list");
const deviceBadge = document.getElementById("device-badge");
const deviceSummary = document.getElementById("device-summary");
const deviceMessage = document.getElementById("device-message");
const sendUsdt = document.getElementById("send-usdt");
const receiveUsdt = document.getElementById("receive-usdt");
const settleCheck = document.getElementById("settle-check");
const workflowMessage = document.getElementById("workflow-message");
const recipientName = document.getElementById("recipient-name");
const recipientFp = document.getElementById("recipient-fp");
const expiry = document.getElementById("expiry");

const OFFLINE_COPY = "Backend offline. I have not reached the dock. Nothing was sent.";
const COPY_YOURSELF = "I did not send this to the other desk. Copy it yourself.";
const API_STORAGE_KEY = "forku-api-base";

let pendingId = null;
let selectedDevice = null;
let activeDevice = null;
let activeRole = null;
let latestBill = null;
let backendOnline = false;
let handcarryPlan = false;
let pinnedBase = null;

function storedBase() {
  try {
    return localStorage.getItem(API_STORAGE_KEY) || "";
  } catch (error) {
    return "";
  }
}

function apiBase() {
  if (pinnedBase !== null) return String(pinnedBase).replace(/\/$/, "");
  const params = new URLSearchParams(window.location.search);
  const fromQuery = (params.get("api") || "").trim();
  if (fromQuery) return fromQuery.replace(/\/$/, "");
  if (window.FORKU_API_BASE) return String(window.FORKU_API_BASE).replace(/\/$/, "");
  return storedBase().replace(/\/$/, "");
}

function api(path) {
  const base = apiBase();
  return base ? base + path : path;
}

function markBackend(state, message) {
  backendOnline = state === "online";
  const el = document.getElementById("backend-state");
  if (el) {
    el.dataset.state = state;
    el.textContent = message;
  }
  if (!backendOnline) {
    const denomination = document.getElementById("denomination");
    const pendingAmount = document.getElementById("pending-amount");
    if (denomination) denomination.textContent = "—";
    if (pendingAmount) {
      pendingAmount.textContent = "—";
      pendingAmount.dataset.pending = "no";
    }
  }
  gate(backendOnline ? latestBill : null);
}

function gate(bill) {
  const online = backendOnline && !!bill;
  const role = online ? bill.role : null;
  const registered = !!(online && bill.device && bill.device.registered);
  if (sendUsdt) sendUsdt.disabled = !(online && role === "A" && registered);
  if (receiveUsdt) receiveUsdt.disabled = !(online && role === "B" && registered);
  const readInvoice = document.getElementById("read-invoice");
  const createInvoice = document.getElementById("create-invoice");
  const acceptPasted = document.getElementById("accept-pasted");
  if (readInvoice) readInvoice.disabled = !(online && role === "A");
  if (createInvoice) createInvoice.disabled = !(online && role === "B");
  if (acceptPasted) acceptPasted.disabled = !(online && role === "B");
  if (settleCheck) settleCheck.disabled = !online;
  if (scanDevice) scanDevice.disabled = !online;
  if (!online) {
    connectDevice.disabled = true;
    registerDevice.disabled = true;
  }
}

function money(cents) {
  return "$" + (Number(cents || 0) / 100).toFixed(2);
}

function confirmationPhraseFor(pending) {
  return "CONFIRM " + pending.id;
}

function line(cls, msg) {
  const li = document.createElement("li");
  li.className = cls;
  li.textContent = msg;
  logEl.appendChild(li);
}

function expiryText(pending) {
  if (pending && pending.expiration_timestamp) {
    return String(pending.expiration_timestamp);
  }
  if (!expiry) return "—";
  return expiry.options[expiry.selectedIndex].textContent + " (preview)";
}

async function fingerprintOf(value) {
  if (!value || !window.crypto || !crypto.subtle) return "";
  const digest = await crypto.subtle.digest(
    "SHA-256",
    new TextEncoder().encode(value),
  );
  const hex = Array.from(new Uint8Array(digest))
    .map(function (byte) {
      return byte.toString(16).padStart(2, "0");
    })
    .join("");
  return hex.slice(0, 8) + "…" + hex.slice(-8);
}

async function renderGenesis(pending) {
  const card = document.getElementById("genesis-card");
  if (!card) return;
  const typed = recipientName ? recipientName.value.trim() : "";
  const recipientId = pending && pending.recipient_id ? String(pending.recipient_id) : "";
  const fp =
    (pending && pending.recipient_fingerprint) ||
    (await fingerprintOf(recipientId || typed));
  const who = typed || "no name given";
  const idPart = recipientId ? " · " + recipientId : "";
  card.textContent = [
    "check_id: " + ((pending && pending.id) || "—"),
    "amount: $5.00",
    "from: dock " + (activeRole || "—"),
    "to: " + who + idPart + " · " + (fp || "fingerprint —"),
    "expires: " + expiryText(pending),
    "status: ISSUED",
  ].join("\n");
  if (recipientFp) {
    recipientFp.textContent = fp
      ? who + " · " + fp
      : "Fingerprint shows up next to the name. An opaque id is not enough.";
  }
}

function renderOffline(check) {
  const list = document.getElementById("offline-checks");
  if (!list || !check || !check.offline) return;
  const order = ["signature_valid", "not_expired", "payee_is_me", "consignment_parses"];
  list.replaceChildren();
  order.forEach(function (key) {
    const row = check.offline[key];
    if (!row) return;
    const item = document.createElement("li");
    item.dataset.check = key;
    item.dataset.ok = row.ok ? "yes" : "no";
    const mark = document.createElement("span");
    mark.className = "mark";
    mark.textContent = row.mark || (row.ok ? "✓" : "✗");
    item.append(mark, document.createTextNode(" " + key.replaceAll("_", " ") + " — " + row.detail));
    list.appendChild(item);
  });
}

function renderLists(bill) {
  const checks = (bill && bill.checks) || [];
  const pendingList = document.getElementById("pending-list");
  const settledList = document.getElementById("settled-list");
  if (pendingList) {
    const pending = checks.filter(function (check) {
      return (
        check.direction !== "out" &&
        (check.state === "ACCEPTED" || check.state === "SETTLING")
      );
    });
    pendingList.replaceChildren();
    if (!pending.length) {
      const empty = document.createElement("li");
      empty.className = "empty";
      empty.textContent = "No pending checks.";
      pendingList.appendChild(empty);
    } else {
      pending.forEach(function (check) {
        pendingList.appendChild(checkRow(check));
      });
    }
  }
  if (settledList) {
    settledList.replaceChildren();
    checks
      .filter(function (check) {
        return check.state === "SETTLED" || check.state === "FAILED" || check.state === "EXPIRED" || check.state === "CONFLICT";
      })
      .forEach(function (check) {
        settledList.appendChild(checkRow(check));
      });
  }
  const nightIn = document.getElementById("night-in");
  const nightOut = document.getElementById("night-out");
  const nightFees = document.getElementById("night-fees");
  let inn = 0;
  let out = 0;
  let fees = 0;
  checks.forEach(function (check) {
    if (check.state !== "SETTLED") return;
    if (check.direction === "out") out += Number(check.amount_cents || 0);
    else inn += Number(check.amount_cents || 0);
    fees += Number(check.fee_sats || 0);
  });
  if (nightIn) nightIn.textContent = (inn / 100).toFixed(2) + " USDT";
  if (nightOut) nightOut.textContent = (out / 100).toFixed(2) + " USDT";
  if (nightFees) nightFees.textContent = fees + " sats";
  const detail = document.getElementById("settle-detail");
  if (detail) {
    const settling = checks.find(function (check) {
      return check.state === "SETTLING";
    });
    const failed = checks.find(function (check) {
      return check.state === "FAILED" || check.state === "EXPIRED" || check.state === "CONFLICT";
    });
    if (settling) detail.textContent = settling.label;
    else if (failed) detail.textContent = failed.state + " — " + (failed.failure || failed.label);
    else detail.textContent = "Nothing is settling.";
  }
  const incoming = checks.find(function (check) {
    return check.direction !== "out" && check.offline;
  });
  if (incoming) renderOffline(incoming);
}

function checkRow(check) {
  const item = document.createElement("li");
  item.dataset.state = check.state || "";
  const amount = document.createElement("strong");
  amount.textContent = money(check.amount_cents);
  const label = document.createElement("span");
  label.textContent = (check.label || check.state || "") + " · " + (check.check_id || "");
  item.append(amount, label);
  return item;
}

function chipState(bill) {
  if (bill.recovery) return "FAILED";
  if (bill.check_state) return bill.check_state;
  if (bill.settlement === "settled") return "SETTLED";
  if (bill.settlement === "failed") return "FAILED";
  if (bill.settlement === "expired") return "EXPIRED";
  if (bill.settlement === "conflict") return "CONFLICT";
  if (bill.settlement === "settling") return "SETTLING";
  if (bill.settlement === "accepted") return "ACCEPTED";
  if (bill.settlement === "issued") return "ISSUED";
  return "";
}

async function refresh() {
  if (!backendOnline) {
    markBackend("offline", OFFLINE_COPY);
    return;
  }
  let bill;
  try {
    const response = await fetch(api("/api/bill"));
    if (!response.ok) throw new Error("bill");
    bill = await response.json();
  } catch (error) {
    markBackend("offline", OFFLINE_COPY);
    return;
  }
  latestBill = bill;
  document.getElementById("denomination").textContent = money(bill.cents);
  const pendingAmount = document.getElementById("pending-amount");
  if (pendingAmount) {
    pendingAmount.textContent = money(bill.pending_cents);
    pendingAmount.dataset.pending = Number(bill.pending_cents) > 0 ? "yes" : "no";
  }
  const state = chipState(bill);
  const chip = document.getElementById("status-chip");
  if (chip) {
    chip.dataset.state = state;
    const current = (bill.checks || []).find(function (check) {
      return check.state === state;
    });
    chip.textContent = (current && current.label) || state || bill.status;
  }
  document.getElementById("status").textContent = bill.status;
  document.getElementById("meta").textContent =
    "role " + bill.role + " · " + bill.identity + " · " + bill.mode;
  renderDevice(bill.device);
  renderLists(bill);
  activeRole = bill.role;
  document.getElementById("workflow-help").textContent =
    bill.role === "A"
      ? "Paste an invoice, or use optional BLE after the puck is registered. Then type the phrase."
      : "Create an invoice and copy it, or accept a pasted consignment. Optional BLE still needs a registered puck.";
  gate(bill);
  if (bill.pending) await renderGenesis(bill.pending);
  else await renderGenesis(null);
}

function renderDevice(device) {
  activeDevice = device || null;
  const record = device && device.device;
  const connection = device && device.connection;
  const address = device && device.active_address;
  deviceBadge.className = "device-badge";
  if (record) {
    const verifiedRegistered =
      connection && connection.connected && connection.address === record.address;
    deviceBadge.textContent = verifiedRegistered ? "Verified" : "Registered";
    deviceBadge.classList.add("ready");
    deviceSummary.textContent =
      record.name + " · " + record.identity + " · " + record.address;
  } else if (address) {
    const verifiedConfigured =
      connection && connection.connected && connection.address === address;
    deviceBadge.textContent = verifiedConfigured ? "Verified" : "Configured";
    deviceBadge.classList.add("configured");
    deviceSummary.textContent =
      "Environment address " + address + " · scan and register it to save this selection.";
  } else {
    deviceBadge.textContent = "Not registered";
    deviceSummary.textContent =
      "Scan for a nearby RgbBill. The tap is BLE. I don't run a phone app for it.";
  }
  connectDevice.disabled = !selectedDevice && !address;
}

function selectedAddress() {
  const checked = deviceList.querySelector('input[name="device-address"]:checked');
  return checked ? checked.value : null;
}

function renderCandidates(devices) {
  deviceList.replaceChildren();
  selectedDevice = null;
  registerDevice.disabled = true;
  const legend = document.createElement("legend");
  legend.textContent = "Nearby checks";
  deviceList.appendChild(legend);
  if (!devices.length) {
    const empty = document.createElement("p");
    empty.className = "empty-device-list";
    empty.textContent = "No authorized RGBill advertisements found.";
    deviceList.appendChild(empty);
    renderDevice(activeDevice);
    return;
  }
  for (const device of devices) {
    const label = document.createElement("label");
    label.className = "device-option";
    const radio = document.createElement("input");
    radio.type = "radio";
    radio.name = "device-address";
    radio.value = device.address;
    if (device.registered) {
      radio.checked = true;
      selectedDevice = device.address;
      registerDevice.disabled = false;
    }
    radio.addEventListener("change", function () {
      selectedDevice = device.address;
      connectDevice.disabled = false;
      registerDevice.disabled = false;
      deviceMessage.textContent =
        "Selected " + device.name + ". Connect to verify or register it now.";
    });
    const description = document.createElement("span");
    const title = document.createElement("strong");
    title.textContent = device.name + (device.registered ? " · registered" : "");
    const details = document.createElement("small");
    details.textContent = device.address + " · RSSI " + device.rssi + " dBm";
    description.append(title, details);
    label.append(radio, description);
    deviceList.appendChild(label);
  }
}

async function postDevice(path, payload) {
  const response = await fetch(api(path), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload || {}),
  });
  const data = await response.json();
  if (!data.ok) throw new Error(data.error || "Device operation failed.");
  return data;
}

scanDevice.addEventListener("click", async function () {
  scanDevice.disabled = true;
  deviceMessage.textContent = "Scanning for authorized RGBill devices…";
  try {
    const data = await postDevice("/api/device/scan", { timeout: 5 });
    renderCandidates(data.devices);
    deviceMessage.textContent = data.count
      ? "Found " + data.count + " authorized check" + (data.count === 1 ? "." : "s.")
      : "No authorized checks found. Check power and keep it nearby.";
  } catch (error) {
    deviceMessage.textContent = error.message;
  } finally {
    scanDevice.disabled = false;
  }
});

connectDevice.addEventListener("click", async function () {
  connectDevice.disabled = true;
  deviceMessage.textContent = "Connecting for a read-only identity check…";
  try {
    const data = await postDevice("/api/device/connect", {
      address: selectedAddress() || (activeDevice && activeDevice.active_address),
    });
    const connection = data.connection;
    deviceMessage.textContent =
      "Verified " + connection.name + " · " + connection.identity + " · " + connection.address;
    if (connection.artifact) {
      const artifact = connection.artifact;
      const kind =
        artifact.kind === 1 ? "invoice" : artifact.kind === 2 ? "consignment" : "empty";
      deviceMessage.textContent +=
        " · " +
        artifact.direction +
        " " +
        kind +
        (artifact.denomination_cents ? " " + money(artifact.denomination_cents) : "");
    }
    renderDevice(data.device);
  } catch (error) {
    deviceMessage.textContent = error.message;
  } finally {
    connectDevice.disabled = !selectedDevice && !(activeDevice && activeDevice.active_address);
  }
});

async function runWorkflow(path) {
  sendUsdt.disabled = true;
  receiveUsdt.disabled = true;
  workflowMessage.textContent = "Inspecting the registered check…";
  try {
    const response = await fetch(api(path), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ cents: 500 }),
    });
    const data = await response.json();
    workflowMessage.textContent = data.reply || data.error || "Step completed.";
    line("bot", workflowMessage.textContent);
    if (data.pending) showConfirm(data.pending);
  } catch (error) {
    workflowMessage.textContent = error.message;
  } finally {
    await refresh();
  }
}

sendUsdt.addEventListener("click", function () {
  runWorkflow("/api/workflow/send");
});
receiveUsdt.addEventListener("click", function () {
  runWorkflow("/api/workflow/receive");
});

if (settleCheck) {
  settleCheck.addEventListener("click", async function () {
    settleCheck.disabled = true;
    workflowMessage.textContent = "Watching the witness…";
    try {
      const response = await fetch(api("/api/rgb/refresh"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: "{}",
      });
      const data = await response.json();
      workflowMessage.textContent = data.ok
        ? "Refresh done. Spendable comes from the wallet. Pending stays pending."
        : data.error || "Settle failed.";
      line("bot", workflowMessage.textContent);
    } catch (error) {
      workflowMessage.textContent = error.message;
    } finally {
      settleCheck.disabled = false;
      await refresh();
    }
  });
}

registerDevice.addEventListener("click", async function () {
  const address = selectedAddress();
  if (!address) return;
  registerDevice.disabled = true;
  deviceMessage.textContent = "Verifying and saving this check…";
  try {
    const data = await postDevice("/api/device/register", { address });
    deviceMessage.textContent = data.reply;
    renderDevice(data.device);
    await refresh();
  } catch (error) {
    deviceMessage.textContent = error.message;
    registerDevice.disabled = false;
  }
});

function showConfirm(pending) {
  pendingId = pending.id;
  handcarryPlan = pending.handcarry === true;
  const phrase = confirmationPhraseFor(pending);
  const typed = recipientName ? recipientName.value.trim() : "";
  confirmNote.textContent =
    pending.note + " Type exactly: " + phrase + (typed ? " Recipient name: " + typed + "." : "");
  confirmPlan.textContent = [
    "amount: $5.00 USDT",
    "base units: " + pending.amount_base_units,
    "balance before: " + money(pending.balance_before_cents),
    "recipient: " + (typed || "no name given") + " · " + pending.recipient_id,
    "fingerprint: " + (pending.recipient_fingerprint || "—"),
    "fee: " + pending.fee_rate_sat_vb + " sat/vB",
    "invoice sha256: " + pending.invoice_sha256,
    "transport endpoints: []",
    "status: ISSUED",
  ].join("\n");
  confirmationPhrase.value = "";
  confirmationPhrase.placeholder = phrase;
  dialog.showModal();
  confirmationPhrase.focus();
  renderGenesis(pending);
}

form.addEventListener("submit", async function (event) {
  event.preventDefault();
  const value = text.value.trim();
  if (!value) return;
  line("you", value);
  text.value = "";
  const res = await fetch(api("/api/chat"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text: value }),
  });
  const data = await res.json();
  line("bot", data.reply || data.error || "Request completed.");
  if (data.pending) showConfirm(data.pending);
  await refresh();
});

confirmForm.addEventListener("submit", async function (event) {
  const submitter = event.submitter;
  if (submitter && submitter.id === "approve" && pendingId) {
    event.preventDefault();
    const res = await fetch(api("/api/confirm"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        id: pendingId,
        phrase: confirmationPhrase.value,
        handcarry: handcarryPlan,
      }),
    });
    const data = await res.json();
    if (data.ok) {
      dialog.close();
      pendingId = null;
      confirmationPhrase.value = "";
      if (data.handcarry && data.handcarry.body) {
        const out = document.getElementById("consignment-out");
        if (out) out.value = data.handcarry.body;
      }
    }
    line(
      "bot",
      data.handcarry
        ? data.handcarry.note || COPY_YOURSELF
        : data.ok && data.completed
          ? "Broadcast complete and exact consignment staged over BLE. Status: ISSUED. Created. Not accepted."
          : data.ok && data.recovery_required
            ? "Broadcast complete. Consignment retained; use retry stage only."
            : data.error,
    );
    await refresh();
  }
});

dialog.addEventListener("close", async function () {
  if (dialog.returnValue === "cancel") {
    const cancelledId = pendingId;
    pendingId = null;
    confirmationPhrase.value = "";
    if (cancelledId) {
      await fetch(api("/api/cancel"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id: cancelledId }),
      });
      line("bot", "Transfer plan cancelled. Nothing was broadcast.");
      await refresh();
    }
  }
});

if (recipientName) {
  recipientName.addEventListener("input", function () {
    renderGenesis(latestBill && latestBill.pending);
  });
}
if (expiry) {
  expiry.addEventListener("change", function () {
    renderGenesis(latestBill && latestBill.pending);
  });
}

async function postJson(path, payload) {
  const response = await fetch(api(path), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload || {}),
  });
  return response.json();
}

async function copyValue(elementId) {
  const field = document.getElementById(elementId);
  const value = field ? field.value : "";
  if (!value) {
    workflowMessage.textContent = "Nothing to copy yet.";
    return;
  }
  try {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(value);
      workflowMessage.textContent = COPY_YOURSELF;
      return;
    }
  } catch (error) {
    workflowMessage.textContent = COPY_YOURSELF;
    return;
  }
  workflowMessage.textContent = COPY_YOURSELF;
}

async function probeBackend() {
  markBackend("checking", "Checking the dock…");
  try {
    const response = await fetch(api("/api/health"), { cache: "no-store" });
    if (!response.ok) throw new Error("health");
    const health = await response.json();
    const coinsOk = !health.coins || health.coins === "mutinynet-test-only";
    if (health.mainnet === true || health.network !== "mutinynet" || !coinsOk) {
      markBackend(
        "offline",
        "This dock is not Mutinynet test coins. I will not spend. Nothing was sent.",
      );
      return null;
    }
    if (health.ok !== true || health.wallet_open === false) {
      markBackend(
        "offline",
        "The dock answered, but the wallet is not open. Nothing was sent.",
      );
      return null;
    }
    markBackend(
      "online",
      "Dock reached. Mutinynet test coins only. Reaching the dock is not a settlement.",
    );
    return health;
  } catch (error) {
    markBackend("offline", OFFLINE_COPY);
    return null;
  }
}

const readInvoice = document.getElementById("read-invoice");
if (readInvoice) {
  readInvoice.addEventListener("click", async function () {
    const invoice = document.getElementById("invoice-in").value.trim();
    readInvoice.disabled = true;
    workflowMessage.textContent = "Planning from the pasted invoice. Nothing is broadcast yet.";
    try {
      const data = await postJson("/api/noradio/plan", { cents: 500, invoice: invoice });
      workflowMessage.textContent = data.reply || data.error || "Plan step finished.";
      line("bot", workflowMessage.textContent);
      if (data.pending) showConfirm(data.pending);
    } catch (error) {
      workflowMessage.textContent = OFFLINE_COPY;
      markBackend("offline", OFFLINE_COPY);
    } finally {
      await refresh();
    }
  });
}

const createInvoice = document.getElementById("create-invoice");
if (createInvoice) {
  createInvoice.addEventListener("click", async function () {
    createInvoice.disabled = true;
    workflowMessage.textContent = "Creating an invoice on this desk only.";
    try {
      const data = await postJson("/api/noradio/invoice", { cents: 500 });
      const carried = data.handcarry || {};
      const field = document.getElementById("invoice-out");
      if (field && carried.invoice) field.value = carried.invoice;
      workflowMessage.textContent = carried.note || data.reply || data.error || COPY_YOURSELF;
      line("bot", workflowMessage.textContent);
    } catch (error) {
      workflowMessage.textContent = OFFLINE_COPY;
      markBackend("offline", OFFLINE_COPY);
    } finally {
      await refresh();
    }
  });
}

const acceptPasted = document.getElementById("accept-pasted");
if (acceptPasted) {
  acceptPasted.addEventListener("click", async function () {
    const encoded = document.getElementById("consignment-in").value.trim();
    acceptPasted.disabled = true;
    workflowMessage.textContent = "Importing the pasted consignment. This does not make it spendable.";
    try {
      const data = await postJson("/api/noradio/import", { consignment_b64: encoded });
      workflowMessage.textContent = data.reply || data.error || "Import finished.";
      line("bot", workflowMessage.textContent);
    } catch (error) {
      workflowMessage.textContent = OFFLINE_COPY;
      markBackend("offline", OFFLINE_COPY);
    } finally {
      await refresh();
    }
  });
}

const copyInvoice = document.getElementById("copy-invoice");
if (copyInvoice) {
  copyInvoice.addEventListener("click", function () {
    copyValue("invoice-out");
  });
}
const copyConsignment = document.getElementById("copy-consignment");
if (copyConsignment) {
  copyConsignment.addEventListener("click", function () {
    copyValue("consignment-out");
  });
}

const backendForm = document.getElementById("backend-form");
if (backendForm) {
  const apiField = document.getElementById("api-base");
  if (apiField && !apiField.value) apiField.value = apiBase();
  backendForm.addEventListener("submit", async function (event) {
    event.preventDefault();
    const value = apiField.value.trim().replace(/\/$/, "");
    pinnedBase = value;
    try {
      if (value) localStorage.setItem(API_STORAGE_KEY, value);
      else localStorage.removeItem(API_STORAGE_KEY);
    } catch (error) {
      /* private mode can refuse storage; the field still applies for this page */
    }
    latestBill = null;
    const health = await probeBackend();
    if (health) await refresh();
  });
}

async function boot() {
  const health = await probeBackend();
  if (health) await refresh();
}

boot();
