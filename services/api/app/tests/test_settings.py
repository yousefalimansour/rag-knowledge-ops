"""Settings hardening: secret redaction + fail-fast on placeholder values in production."""

from __future__ import annotations

import pytest

from app.core.config import Settings


def test_safe_dump_redacts_secret_fields():
    s = Settings(SECRET_KEY="abc123", JWT_SECRET="def456", GOOGLE_API_KEY="key789")
    dumped = s.safe_dump()
    assert dumped["SECRET_KEY"] == "***"
    assert dumped["JWT_SECRET"] == "***"
    assert dumped["GOOGLE_API_KEY"] == "***"
    # Non-secret fields stay intact.
    assert dumped["GEMINI_MODEL"] == "gemini-2.5-flash"


def test_repr_does_not_expose_secret_values():
    s = Settings(SECRET_KEY="topsecret-please", JWT_SECRET="jwt-real")
    text = repr(s)
    assert "topsecret-please" not in text
    assert "jwt-real" not in text
    assert "***" in text


def test_safe_dump_redacts_database_url_with_password():
    s = Settings(DATABASE_URL="postgresql+asyncpg://kops:hunter22@db:5432/kops")
    assert s.safe_dump()["DATABASE_URL"] == "***"


def test_production_requires_real_secrets():
    with pytest.raises(ValueError) as exc:
        # Explicitly pass placeholders so the env-var defaults from conftest
        # don't accidentally satisfy the check.
        Settings(
            APP_ENV="production",
            SECRET_KEY="change-me",
            JWT_SECRET="change-me-jwt",
            GOOGLE_API_KEY="",
        )
    msg = str(exc.value).lower()
    assert "secret_key" in msg
    assert "jwt_secret" in msg
    assert "google_api_key" in msg


def test_production_with_real_secrets_succeeds():
    s = Settings(
        APP_ENV="production",
        SECRET_KEY="32-chars-of-actual-randomness-xx",
        JWT_SECRET="32-chars-of-jwt-randomness-yyyyz",
        GOOGLE_API_KEY="AIza-real-looking-key",
    )
    assert s.is_production


def test_dev_with_placeholders_does_not_raise():
    # Default APP_ENV=development must accept placeholders so the demo boots.
    s = Settings()
    assert not s.is_production
