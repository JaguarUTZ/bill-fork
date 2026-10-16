# No-radio dock (Mutinynet test coins only)

Two browser sessions can create, accept, and settle a $5 check without the BLE
puck. Each browser talks only to its own dock. You copy the invoice and the
consignment from one page to the other. The docks do not POST those bytes to
each other, and the tap path still sends `transport_endpoints=[]`.

BLE scan / connect / register stays on the page and is optional.

Accepted is not settled. The yellow line is exactly
`ACCEPTED - NOT YET SETTLED ON-CHAIN`. That amount stays under Pending and is
not spendable. Cancelling does not cost more than creating. See
[CHECK-GUARANTEES.md](CHECK-GUARANTEES.md).

This money is Mutinynet test money. There is no mainnet path in this process.

## What you provide

This repo does not include a host, a funded wallet, or a mnemonic.

- A machine you control (a small VM or your laptop) with Python 3.12, or Docker.
- Two role environments from `scripts/rgb_provision.py` (below). The script
  prints paths and file modes. It does not print mnemonic words. Those files
  stay out of git (`secrets/`, `wallet-data/`, `.env.a`, `.env.b`).
- Mutinynet test BTC for fees, and one RGB asset on Bill A. Funding steps are
  below. They move test coins only after you run them.
- `RGB_ASSET_ID` and `RGB_ASSET_PRECISION` for that asset.
- If a static page (Vercel or otherwise) will call the dock from another
  origin: the public origin of that page, set as `DOCK_CORS_ORIGIN`.

## Run locally

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt -r requirements-rgb.txt
.venv/bin/python scripts/rgb_provision.py --role A
.venv/bin/python scripts/rgb_provision.py --role B
```

Put `RGB_ASSET_ID` in each role file after the asset exists. `chmod 600` the
mnemonic files if the mode is not already `0600`. The wallet reader refuses a
looser mode.

Role A, then role B (the indexer answers HTTP 429 if both come up together):

```bash
set -a; source .env.a; set +a
export DOCK_HTTP_PORT=8788
export DOCK_CORS_ORIGIN=https://your-app.vercel.app   # omit for same-origin
.venv/bin/python scripts/run_dock.sh
```

```bash
set -a; source .env.b; set +a
export DOCK_HTTP_PORT=8789
export BILL_ROLE=B
.venv/bin/python scripts/run_dock.sh
```

`scripts/run_dock.sh` refuses an `ELECTRUM_URL` that is not a Mutinynet host
and refuses `RGB_MNEMONIC` or `MNEMONIC` in the environment.

Health (this does not contact the indexer):

```bash
curl -sS http://127.0.0.1:8788/api/health
```

Expect `"network": "mutinynet"`, `"mainnet": false`, `"coins": "mutinynet-test-only"`,
`"noradio": true`, `"indexer": "not-probed"`. `ok` is true only after the
wallet process is open.

## Docker

```bash
docker build -t forku-dock .
```

The image installs `rgb-lib==0.3.0b7`. If that pin has no wheel for the image
platform, the build fails. Do not replace the pin.

The image listens on `0.0.0.0:8788` inside the container so a published port
works. Publish it on loopback unless you mean to expose an unauthenticated
wallet UI:

```bash
docker run --rm \
  -p 127.0.0.1:8788:8788 \
  -e BILL_ROLE=A \
  -e ELECTRUM_URL=https://mutinynet.com/api \
  -e RGB_OOB_CONSIGNMENT=1 \
  -e RGB_DATA_DIR_A=/var/lib/forku/bill-a \
  -e RGB_DATA_DIR_B=/var/lib/forku/bill-b \
  -e RGB_OOB_INBOX_A=/var/lib/forku/oob-a \
  -e RGB_MASTER_FINGERPRINT_A \
  -e RGB_MNEMONIC_FILE_A=/var/lib/forku/secrets/bill-a.mnemonic \
  -e RGB_ASSET_ID \
  -e RGB_ASSET_PRECISION=6 \
  -e DOCK_CORS_ORIGIN=https://your-app.vercel.app \
  -v "$PWD/wallet-data:/var/lib/forku" \
  -v "$PWD/secrets:/var/lib/forku/secrets:ro" \
  forku-dock
```

The container user is uid `10001`. The mounted wallet directory has to be
writable by that uid, and the mnemonic file has to be readable by it while
staying mode `0600`. Run a second container for role B on
`127.0.0.1:8789` with `BILL_ROLE=B` and the B credential variables. Do not put
mnemonic words in `-e`.

## Fund (you run this; nothing here is pre-funded)

1. Bitcoin test coins for fees. The public Mutinynet faucet is
   [https://faucet.mutinynet.com](https://faucet.mutinynet.com). Confirm it is
   still up, then send coins to an address from
   `.venv/bin/python -m scripts.rgb_wallet status` in the role A environment.
2. RGB on Bill A only, and only as a funding receive. This is the one call
   that sets a transport endpoint, and only because the faucet proxy has to
   deliver the asset. The check path does not use it.

   ```bash
   set -a; source .env.a; set +a
   .venv/bin/python -m scripts.rgb_wallet receive --bootstrap
   ```

   The command prints an invoice. Give that invoice to the RGB faucet that
   speaks `RGB_BOOTSTRAP_PROXY` (`rpcs://proxy.kaleidoswap.com/json-rpc` unless
   you override it). Then set `RGB_ASSET_ID` to the asset you received.
3. Bill B needs Mutinynet BTC for its own witness fees before it can settle.
   Same faucet, role B's address. Do not bootstrap an RGB asset into B unless
   you intend B to hold one.

## Static page

Host `web/static/` on Vercel (or open it behind any static host). Point the
Backend field at the dock, or open `https://your-app.vercel.app/?api=https://dock.example:8788`.
The page stores that base in `localStorage` under `forku-api-base` when you
save it. `window.FORKU_API_BASE` overrides storage when no query is present.

`DOCK_CORS_ORIGIN` must be that page's exact origin (`https://host`, no path,
no `*`). Any other origin gets no `Access-Control-Allow-Origin` header. If the
dock cannot be reached, or it is not Mutinynet, the page says
`Backend offline. I have not reached the dock. Nothing was sent.` and shows
spendable and pending as `—`.

## Hand-carry

1. On B, Create invoice. Copy the text. The page says it did not send it.
2. On A, paste that one line and Plan from pasted invoice. Type the phrase the
   page builds (`CONFIRM` plus the plan id). The server does not return the phrase.
3. Copy the consignment from A into B and Accept pasted consignment. Yellow
   pending. Not spendable.
4. Settle calls `/api/rgb/refresh`. Green is only the settled state, after the
   wallet reports it.

Optional BLE still uses Issue check / Accept over BLE and still requires a
registered puck.

## End-to-end script

```bash
E2E_FORCE_MOCK=1 python3 scripts/e2e_check.py
```

Prints `E2E_NETWORK=mock` and `coins_moved=0`. A live run is opt-in and uses
the docks you already started:

```bash
E2E_LIVE=1 E2E_URL_A=http://127.0.0.1:8788 E2E_URL_B=http://127.0.0.1:8789 \
  python3 scripts/e2e_check.py
```

That live command broadcasts a real Mutinynet test send on those wallets.
Do not point it at mainnet. There is no mainnet setting to point.
