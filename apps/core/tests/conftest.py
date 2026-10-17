"""Shared fixtures: every test sees the code defaults, never the developer's shell or .env."""

import pytest

from regista_core.config import Settings, get_settings


@pytest.fixture(autouse=True)
def _isolated_settings(monkeypatch):
    for name in Settings.model_fields:
        monkeypatch.delenv(name.upper(), raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def offline_settings() -> Settings:
    """Settings built from code defaults only (no .env file)."""
    return Settings(_env_file=None)
