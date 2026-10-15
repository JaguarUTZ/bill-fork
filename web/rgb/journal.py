"""Crash journal for a consignment that has already been broadcast.

The file records the on-disk consignment path after ``send`` returns and
before BLE staging. A crash in that window can be resumed with retry-stage.
The journal does not prove the transaction is still the one miners will
confirm, and it cannot recover a crash that happens before the journal itself
is fsynced.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from web.rgb.adapter import ConsignmentArtifact


class JournalError(RuntimeError):
    """The journal exists but cannot be trusted as a recovery pointer."""


@dataclass(frozen=True)
class JournaledConsignment:
    cents: int
    artifact: ConsignmentArtifact


class ConsignmentJournal:
    """One JSON file, replaced atomically, mode 0600."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> JournaledConsignment | None:
        if not self.path.exists():
            return None
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            artifact_path = Path(payload["path"])
            size = int(payload["size"])
            digest = str(payload["sha256"])
            cents = int(payload["cents"])
            txid = str(payload["txid"])
            batch = int(payload["batch_transfer_idx"])
            version = int(payload["version"])
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            raise JournalError(
                "in-flight consignment journal is unreadable; inspect the wallet "
                "before creating another send"
            ) from exc
        if version != 1 or cents <= 0 or not txid or size < 1 or not digest:
            raise JournalError("in-flight consignment journal failed validation")
        try:
            body = artifact_path.read_bytes()
        except OSError as exc:
            raise JournalError(
                "journal points at a consignment file that cannot be read; "
                f"path={artifact_path}"
            ) from exc
        if len(body) != size or hashlib.sha256(body).hexdigest() != digest:
            raise JournalError(
                "journal consignment bytes do not match the recorded hash; "
                f"path={artifact_path}"
            )
        return JournaledConsignment(
            cents,
            ConsignmentArtifact(
                txid=txid,
                batch_transfer_idx=batch,
                path=artifact_path.resolve(),
                size=size,
                sha256=digest,
            ),
        )

    def store(self, entry: JournaledConsignment) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        os.chmod(self.path.parent, 0o700)
        body = {
            "version": 1,
            "cents": entry.cents,
            "txid": entry.artifact.txid,
            "batch_transfer_idx": entry.artifact.batch_transfer_idx,
            "path": str(entry.artifact.path),
            "size": entry.artifact.size,
            "sha256": entry.artifact.sha256,
        }
        encoded = json.dumps(body, sort_keys=True).encode("utf-8")
        fd, temporary = tempfile.mkstemp(
            dir=self.path.parent,
            prefix=".pending-consignment-",
            suffix=".json",
        )
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temporary, 0o600)
            os.replace(temporary, self.path)
            os.chmod(self.path, 0o600)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def clear(self) -> None:
        try:
            self.path.unlink()
        except FileNotFoundError:
            return
