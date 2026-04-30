# syntax=docker/dockerfile:1.7

FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
 && apt-get install -y --no-install-recommends curl build-essential libpq-dev \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /srv

# Worker imports `app.*` from the api tree, so we need both source roots.
COPY services/api/ ./api/
COPY services/worker/ ./worker/
COPY seed/ /srv/seed/

RUN pip install --upgrade pip \
 && pip install -e ./api \
 && pip install -e ./worker

# Both packages on PYTHONPATH so `from app.core.config import ...` works.
ENV PYTHONPATH=/srv/api:/srv/worker

# Non-root runtime user; share the gid with the api image so the shared
# uploads volume is read/write to both.
RUN groupadd --system --gid 10001 kops \
 && useradd --system --uid 10001 --gid 10001 --create-home kops \
 && mkdir -p /srv/uploads \
 && chown -R kops:kops /srv

USER kops

WORKDIR /srv/worker
