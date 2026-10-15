# What a tap transfer guarantees

This dock does not implement an offline check. It delivers an RGB consignment
for a witness transaction that Bill A's wallet has already broadcast. Read
this before treating a tap as payment.

## What is not guaranteed

Cancelling or destroying the transfer is **not** enforced to cost more than
creating it.

- Creating it calls rgb-lib 0.3.0b7 `Wallet.send`, which builds and broadcasts
  the Bitcoin witness transaction immediately. The sender pays a miner fee at
  `RGB_FEE_RATE` sat/vB plus the `RGB_WITNESS_AMOUNT_SAT` witness output. This
  code does not inspect the signed transaction, so it does not quote a fee in
  satoshis and it does not know whether the transaction signals replace-by-fee.
- A conflicting spend of those inputs, before the receiver's wallet reports
  the transfer settled, can drop the broadcast. This dock does not build that
  spend. It also cannot make that spend cost more than the original: the
  pinned `Wallet.send` API has no CLTV or tapscript escrow, no penalty bond,
  and no switch that disables replacement. A replacement can pay a fee and
  omit the witness output, so the sender can get the witness sats back.
- The receiver cannot validate, offline, that the broadcast is still funded.
  Consignment import uses the indexer. BLE carries the bytes with a CRC-32.
  Link encryption, when the new firmware is flashed, rejects unpaired GATT
  access. It does not authenticate the peer (Just Works, no passkey, no
  numeric comparison), and the bill display's `denomination_cents` field is
  not a signature over the amount.
- A Mutinynet confirmation is not economic finality. Mutinynet is a custom
  signet with a centralized signer. One confirmation is the wallet's
  configured threshold (`RGB_MIN_CONFIRMATIONS`, minimum 1). It is not a
  claim that reorganization is expensive.
- The in-flight consignment journal recovers a crash after the journal file
  is fsynced and before BLE staging finishes. A crash before that fsync can
  still lose the app's pointer. The journal does not prove miners will
  confirm that transaction.
- The HTTP session token stops a browser page on another origin, and a client
  that does not have the token, from calling the dock. It does not stop a
  process on the dock machine that can read the page the browser loaded.

`cancel_costs_more_than_create` and `offline_validation` are false in the
plan payload on purpose. Do not report them as true.

## What the software does enforce

- Bill B's spendable balance is the wallet's spendable balance. Importing a
  consignment does not add the expected $5. A transfer the wallet reports as
  waiting is **accepted, unsettled** and is not spendable. `failed` and
  `expired` stay their own states.
- The sender confirms a per-plan secret that is not derived from the plan id.
  State-changing HTTP requests must send `Content-Type: application/json`,
  `X-Dock-Session`, and a Host (and Origin, if present) on the bind
  allow-list. `GET /api/bill` omits the confirmation secret without that
  session header. The body size is capped at 65536 bytes.
- After broadcast, `/api/cancel` is not a way to unspend. Cancel only drops
  a plan that has not been consumed.
- Startup does not label the wallet settled unless `list_transfers` succeeds
  and every recorded transfer is settled. If the list cannot be read, the
  settlement is `unknown`. A journaled consignment reopens stage recovery
  instead of a new send.
- The amount that will be broadcast is the confirmed $5.00 plan. The bill's
  `denomination_cents` metadata is shown as an unauthenticated display value.
- The confirmation screen shows the invoice `recipient_id` and says the BLE
  hop did not authenticate that payee.

## What it would take for cancel to cost more

A real check would lock the funds on chain so the sender cannot take them
back before a timelock without a loss greater than the cost of creating the
lock: for example an RGB assignment on a tapscript where the receiver can
claim and the sender can refund only after N blocks, or a confirmed
collateral output that a conflicting spend destroys. rgb-lib 0.3.0b7's send
API does not build that contract. This repository does not pretend to.
