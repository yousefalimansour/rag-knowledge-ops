# syntax=docker/dockerfile:1.7

FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
 && apt-get install -y --no-install-recommends curl build-essential libpq-dev \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /srv/api

# Editable install needs the package source to exist before install,
# so we COPY first. The compose bind-mount keeps live-reload working in dev.
COPY services/api/ ./

RUN pip install --upgrade pip \
 && pip install -e ".[dev]"

# Seed fixtures live at /srv/seed in the image so `python -m app.scripts.seed`
# works without depending on the host filesystem layout.
COPY seed/ /srv/seed/

# Non-root runtime user. uid/gid 10001 must match the worker image so the
# shared `uploads_data` named volume is read/write from both containers.
RUN groupadd --system --gid 10001 kops \
 && useradd --system --uid 10001 --gid 10001 --create-home kops \
 && mkdir -p /srv/uploads \
 && chown -R kops:kops /srv/api /srv/uploads /srv/seed

USER kops

EXPOSE 8000

# `--proxy-headers` honors X-Forwarded-* from the compose network or any
# upstream proxy; `--forwarded-allow-ips=*` is fine inside the private network
# (we don't expose uvicorn directly to the public internet).
CMD ["bash", "-c", "python -m app.scripts.wait_for_db && alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips=*"]
