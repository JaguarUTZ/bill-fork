# One Mutinynet dock process. BLE is optional; the no-radio API is HTTP.
# Build from the repo root:
#   docker build -t forku-dock .
# The rgb-lib wheel is pinned in requirements-rgb.txt. If that wheel does not
# publish a build for this image's platform, the build stops there — do not
# swap in another version.

FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    BILL_ROLE=A \
    ELECTRUM_URL=https://mutinynet.com/api \
    RGB_OOB_CONSIGNMENT=1 \
    DOCK_HTTP_HOST=0.0.0.0 \
    DOCK_HTTP_PORT=8788

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates libssl3 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt requirements-rgb.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-rgb.txt

COPY dock ./dock
COPY web ./web
COPY scripts ./scripts

RUN useradd --create-home --uid 10001 dock \
    && mkdir -p /var/lib/forku \
    && chown -R dock:dock /var/lib/forku
USER dock

EXPOSE 8788
CMD ["python", "-m", "web.server"]
