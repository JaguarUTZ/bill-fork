/**
 * Screenshot the Forkashi skin against mocked GET /api/bill payloads.
 * Does not import the dock, the wallet, or Mutinynet.
 *
 *   node scripts/capture_skin_shots.mjs [output-dir]
 */
import { spawn } from "node:child_process";
import { createServer } from "node:http";
import { readFileSync, mkdirSync, writeFileSync } from "node:fs";
import { dirname, extname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const staticDir = join(root, "web", "static");
const fixtures = JSON.parse(
  readFileSync(join(root, "scripts", "skin_fixtures", "bills.json"), "utf8"),
);
const outDir = resolve(process.argv[2] || "/tmp/skin-shots");
mkdirSync(outDir, { recursive: true });

const types = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".ttf": "font/ttf",
  ".txt": "text/plain; charset=utf-8",
  ".svg": "image/svg+xml",
  ".json": "application/json",
};

let current = "none";

const server = createServer((req, res) => {
  const url = new URL(req.url || "/", "http://127.0.0.1");
  if (url.pathname === "/api/bill") {
    const body = JSON.stringify(fixtures[current]);
    res.writeHead(200, {
      "Content-Type": "application/json",
      "Cache-Control": "no-store",
    });
    res.end(body);
    return;
  }
  const rel = url.pathname === "/" ? "/index.html" : url.pathname;
  const file = join(staticDir, decodeURIComponent(rel));
  if (!file.startsWith(staticDir)) {
    res.writeHead(403);
    res.end("no");
    return;
  }
  try {
    const data = readFileSync(file);
    res.writeHead(200, {
      "Content-Type": types[extname(file)] || "application/octet-stream",
      "Cache-Control": "no-store",
    });
    res.end(data);
  } catch {
    res.writeHead(404);
    res.end("missing");
  }
});

await new Promise((resolveListen) => server.listen(0, "127.0.0.1", resolveListen));
const { port } = server.address();
const origin = `http://127.0.0.1:${port}`;

const chrome = spawn(
  "google-chrome",
  [
    "--headless=new",
    "--no-sandbox",
    "--disable-gpu",
    "--disable-dev-shm-usage",
    "--remote-debugging-port=0",
    "--user-data-dir=/tmp/forkashi-chrome-profile",
    "about:blank",
  ],
  { stdio: ["ignore", "pipe", "pipe"] },
);

const debugPort = await new Promise((resolvePort, rejectPort) => {
  const timer = setTimeout(() => rejectPort(new Error("chrome did not open a port")), 15000);
  const onData = (buf) => {
    const text = buf.toString();
    const match = text.match(/DevTools listening on ws:\/\/127\.0\.0\.1:(\d+)\//);
    if (match) {
      clearTimeout(timer);
      resolvePort(Number(match[1]));
    }
  };
  chrome.stderr.on("data", onData);
  chrome.stdout.on("data", onData);
});

const version = await (await fetch(`http://127.0.0.1:${debugPort}/json/version`)).json();
const browser = new WebSocket(version.webSocketDebuggerUrl);
await new Promise((resolveOpen) => browser.addEventListener("open", resolveOpen));

const pending = new Map();
let nextId = 1;
browser.addEventListener("message", (event) => {
  const message = JSON.parse(event.data);
  if (!message.id || !pending.has(message.id)) return;
  const { resolve, reject } = pending.get(message.id);
  pending.delete(message.id);
  if (message.error) reject(new Error(JSON.stringify(message.error)));
  else resolve(message.result);
});

function send(method, params = {}, sessionId) {
  const id = nextId++;
  const payload = { id, method, params };
  if (sessionId) payload.sessionId = sessionId;
  browser.send(JSON.stringify(payload));
  return new Promise((resolve, reject) => pending.set(id, { resolve, reject }));
}

async function shot(name, { fixture, hash, width, height, focus, waitFor }) {
  current = fixture;
  const created = await send("Target.createTarget", { url: "about:blank" });
  const attached = await send("Target.attachToTarget", {
    targetId: created.targetId,
    flatten: true,
  });
  const sessionId = attached.sessionId;
  await send("Page.enable", {}, sessionId);
  await send(
    "Emulation.setDeviceMetricsOverride",
    { width, height, deviceScaleFactor: 1, mobile: width < 500 },
    sessionId,
  );
  await send("Page.navigate", { url: `${origin}/${hash}` }, sessionId);
  const started = Date.now();
  let value = "";
  while (Date.now() - started < 8000) {
    const evaluated = await send(
      "Runtime.evaluate",
      { expression: waitFor, returnByValue: true },
      sessionId,
    );
    value = evaluated.result && evaluated.result.value;
    if (value) break;
    await new Promise((r) => setTimeout(r, 100));
  }
  if (!value) throw new Error(`${name} timed out waiting for ${waitFor}`);
  if (focus) {
    await send(
      "Runtime.evaluate",
      { expression: focus, returnByValue: true },
      sessionId,
    );
  }
  const probe = await send(
    "Runtime.evaluate",
    {
      expression: `JSON.stringify({
        steps: [...document.querySelectorAll("#step-rail li")].map((li) => li.className),
        kind: document.getElementById("pay-state") && document.getElementById("pay-state").dataset.kind,
        bg: document.getElementById("pay-state") && getComputedStyle(document.getElementById("pay-state")).backgroundColor,
        outline: document.activeElement && getComputedStyle(document.activeElement).outlineColor
      })`,
      returnByValue: true,
    },
    sessionId,
  );
  if (probe.result && probe.result.value) console.log("  " + probe.result.value);
  await new Promise((r) => setTimeout(r, 250));
  const overflow = await send(
    "Runtime.evaluate",
    {
      expression:
        "document.documentElement.scrollWidth <= document.documentElement.clientWidth + 2",
      returnByValue: true,
    },
    sessionId,
  );
  const image = await send(
    "Page.captureScreenshot",
    { format: "png", fromSurface: true },
    sessionId,
  );
  const file = join(outDir, `${name}.png`);
  writeFileSync(file, Buffer.from(image.data, "base64"));
  await send("Target.closeTarget", { targetId: created.targetId });
  const fits = overflow.result && overflow.result.value === true;
  console.log(`${name} ${value} overflow=${fits ? "no" : "YES"} -> ${file}`);
  if (!fits) throw new Error(`${name} overflows horizontally`);
}

const titleOf = (text) =>
  `document.getElementById("pay-title") && document.getElementById("pay-title").textContent === ${JSON.stringify(text)} && document.getElementById("sound-toggle").textContent === "Sound: OFF"`;

try {
  await shot("desktop_nothing_sent", {
    fixture: "none",
    hash: "#desk",
    width: 1280,
    height: 1100,
    focus: "document.getElementById('sound-toggle').focus({focusVisible:true})",
    waitFor: titleOf("Nothing sent yet"),
  });
  await shot("mobile_nothing_sent", {
    fixture: "none",
    hash: "#desk",
    width: 360,
    height: 1400,
    waitFor: titleOf("Nothing sent yet"),
  });
  await shot("badge_sent", {
    fixture: "sent",
    hash: "#desk",
    width: 1280,
    height: 1100,
    waitFor: titleOf("Sent. Waiting for the other bill to import it"),
  });
  await shot("badge_accepted", {
    fixture: "accepted",
    hash: "#desk",
    width: 1280,
    height: 1100,
    waitFor: titleOf("Accepted — not yet settled on-chain"),
  });
  await shot("badge_settled", {
    fixture: "settled",
    hash: "#desk",
    width: 1280,
    height: 1100,
    waitFor: titleOf("SETTLED ON-CHAIN. Final."),
  });
  await shot("badge_attention", {
    fixture: "attention",
    hash: "#desk",
    width: 1280,
    height: 1100,
    waitFor:
      titleOf("Needs attention") +
      ' && document.getElementById("pay-detail").textContent.includes("retry-consignment-import")',
  });
  await shot("learn_card", {
    fixture: "accepted",
    hash: "#learn=accepted",
    width: 1280,
    height: 1100,
    waitFor:
      'document.getElementById("learn-dialog").open && document.getElementById("learn-pause").textContent === "Game paused. Nothing is sent while you read." && document.body.innerText.includes("still needs internet to import the check")',
  });
  await shot("mobile_learn_card", {
    fixture: "none",
    hash: "#learn=check",
    width: 360,
    height: 900,
    waitFor:
      'document.getElementById("learn-dialog").open && document.getElementById("learn-title").textContent.includes("check")',
  });
  await shot("splash", {
    fixture: "none",
    hash: "",
    width: 1280,
    height: 900,
    waitFor:
      'document.getElementById("splash").open && document.getElementById("splash-title").textContent === "Press start" && document.getElementById("splash-sound").textContent === "Sound: OFF"',
  });
  await shot("howto", {
    fixture: "none",
    hash: "#howto",
    width: 1280,
    height: 1100,
    waitFor:
      'document.getElementById("howto-dialog").open && document.querySelectorAll("#howto-list .pixel-art").length === 4',
  });
  const created = await send("Target.createTarget", { url: "about:blank" });
  const attached = await send("Target.attachToTarget", {
    targetId: created.targetId,
    flatten: true,
  });
  const sessionId = attached.sessionId;
  await send("Page.enable", {}, sessionId);
  await send(
    "Emulation.setDeviceMetricsOverride",
    { width: 1280, height: 900, deviceScaleFactor: 1, mobile: false },
    sessionId,
  );
  current = "none";
  await send("Page.navigate", { url: `${origin}/#desk` }, sessionId);
  const started = Date.now();
  let ready = false;
  while (Date.now() - started < 8000) {
    const evaluated = await send(
      "Runtime.evaluate",
      {
        expression:
          'document.getElementById("pay-title") && document.getElementById("pay-title").textContent === "Nothing sent yet"',
        returnByValue: true,
      },
      sessionId,
    );
    if (evaluated.result && evaluated.result.value) {
      ready = true;
      break;
    }
    await new Promise((r) => setTimeout(r, 100));
  }
  if (!ready) throw new Error("interaction page did not load");
  const interaction = await send(
    "Runtime.evaluate",
    {
      expression: `(async () => {
        const toggle = document.getElementById("sound-toggle");
        const before = toggle.textContent;
        toggle.click();
        const on = toggle.textContent === "Sound: ON" && toggle.getAttribute("aria-pressed") === "true";
        toggle.click();
        const off = toggle.textContent === "Sound: OFF" && toggle.getAttribute("aria-pressed") === "false";
        document.querySelector('[data-learn="check"]').click();
        const dialog = document.getElementById("learn-dialog");
        const opened = dialog.open && document.getElementById("learn-pause").textContent.startsWith("Game paused");
        const focused = dialog.contains(document.activeElement);
        dialog.close();
        const closed = !dialog.open;
        const stored = localStorage.getItem("forkashi-sound");
        document.getElementById("lang-es").click();
        const spanish = document.getElementById("pay-title").textContent;
        document.querySelector('[data-learn="accepted"]').click();
        const spanishPause = document.getElementById("learn-pause").textContent;
        document.getElementById("learn-dialog").close();
        window.forkashiSkin.bill({ settlement: "waiting-import", recovery: null, role: "B", pending: null, receipts: [] });
        const waitingImport = document.getElementById("pay-title").textContent;
        window.forkashiSkin.bill({ settlement: "unknown", recovery: null, role: "A", pending: null, receipts: [] });
        const unknown = document.getElementById("pay-title").textContent;
        window.forkashiSkin.bill({ settlement: "settled", recovery: { action: "inspect-wallet-before-any-new-plan" }, role: "A", pending: null, receipts: [] });
        const recoveryWins = document.getElementById("pay-title").textContent + "|" + document.getElementById("pay-detail").textContent;
        document.getElementById("lang-en").click();
        return JSON.stringify({ before, on, off, opened, focused, closed, stored, spanish, spanishPause, waitingImport, unknown, recoveryWins });
      })()`,
      awaitPromise: true,
      returnByValue: true,
    },
    sessionId,
  );
  console.log("interaction " + (interaction.result && interaction.result.value));
  const report = JSON.parse(interaction.result.value);
  if (!report.on || !report.off || !report.opened || !report.focused || !report.closed) {
    throw new Error("skin interaction failed: " + interaction.result.value);
  }
  if (report.stored !== "off") throw new Error("sound storage was " + report.stored);
  if (report.spanish !== "Todavía no se envió nada") {
    throw new Error("spanish badge was " + report.spanish);
  }
  if (report.spanishPause !== "Juego en pausa. No se envía nada mientras lees.") {
    throw new Error("spanish pause was " + report.spanishPause);
  }
  if (report.waitingImport !== "Aceptado — aún no liquidado en la cadena") {
    throw new Error("waiting-import badge was " + report.waitingImport);
  }
  if (report.unknown !== "Necesita atención") {
    throw new Error("unknown badge was " + report.unknown);
  }
  if (!report.recoveryWins.startsWith("Necesita atención|inspect-wallet-before-any-new-plan")) {
    throw new Error("recovery badge was " + report.recoveryWins);
  }
  await send("Target.closeTarget", { targetId: created.targetId });
  console.log("shots ok");
} finally {
  browser.close();
  chrome.kill("SIGKILL");
  server.close();
}
