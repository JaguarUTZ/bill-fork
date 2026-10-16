#!/bin/sh
# Start one dock process. Mutinynet only. The mnemonic stays in a file.
set -eu
cd "$(dirname "$0")/.."

if [ -n "${RGB_MNEMONIC:-}" ] || [ -n "${MNEMONIC:-}" ]; then
  echo "refusing to start: put the mnemonic in a chmod 600 file, not RGB_MNEMONIC or MNEMONIC" >&2
  exit 1
fi

if [ -n "${ELECTRUM_URL:-}" ]; then
  case "$ELECTRUM_URL" in
    *mutinynet.com*) ;;
    *)
      echo "refusing to start: ELECTRUM_URL must be a Mutinynet host" >&2
      exit 1
      ;;
  esac
fi

PYTHON="${PYTHON:-python3}"
exec "$PYTHON" -m web.server
