# Check guarantees (this build)

FORKU2BTC is a skin and status desk on Edwin Kestler's RGB cash bill
(github.com/EdwinKestler/bill). Mutinynet only. Test money. No production
network.

## What this build does not guarantee

The cost-asymmetry idea — that cancelling or undoing a check costs the sender
more than creating it — **does not hold** today. There is no escrow and no
timelock in this fork. The desk must not say that it holds.

Accepted means the receiving desk took the check in. It does not mean the
witness is confirmed, the funds were locked, or the sender can no longer
cancel. Until the check is SETTLED, the sender could still cancel.

Offline, this desk cannot prove the funds exist or are unspent. A valid-looking
check is not a proof of funds.

## Status machine

| State | Label | Spendable? |
| --- | --- | --- |
| ISSUED | Created. Not accepted. | No |
| ACCEPTED | ACCEPTED - NOT YET SETTLED ON-CHAIN | No. Shown under Pending, in yellow. |
| SETTLING | Seen on-chain, n/N confirmations | No |
| SETTLED | SETTLED | Only the wallet's spendable figure moves, and only after confirmations. |
| FAILED | FAILED | No. Never shown as waiting. |
| EXPIRED | EXPIRED | No. Never shown as waiting. |
| CONFLICT | CONFLICT | No. Never shown as waiting. |

rgb-lib `failed` maps to FAILED. Import does not add the check amount to the
spendable balance. Pending checks are stored and shown again after a restart;
restart does not mark them settled and does not call the network to do it.

## Credit

Built on Edwin Kestler's bill / O2A. There is no upstream LICENSE in the
source this fork was taken from. Ask Edwin before redistributing.
