FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
 && apt-get install -y --no-install-recommends curl build-essential libpq-dev \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /srv

# Copy both source trees first — worker depends on `app.*` from the api tree.
COPY services/api/ ./api/
COPY services/worker/ ./worker/

RUN pip install --upgrade pip \
 && pip install -e ./api \
 && pip install -e ./worker

# Both packages on PYTHONPATH so the worker can `from app.core.config import ...`.
ENV PYTHONPATH=/srv/api:/srv/worker

WORKDIR /srv/worker
