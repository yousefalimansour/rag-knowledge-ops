FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
 && apt-get install -y --no-install-recommends curl build-essential libpq-dev \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /srv/api

# Copy source first (editable install needs the package to exist),
# then install. Slower cold builds, but correct, and a bind-mount in
# compose keeps hot-reload fast for day-to-day work.
COPY services/api/ ./

RUN pip install --upgrade pip \
 && pip install -e ".[dev]"

EXPOSE 8000

CMD ["bash", "-c", "python -m app.scripts.wait_for_db && alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers"]
