"""Settings and logging: offline defaults, .env parsing, and .env.example kept in sync."""

import json
import logging
from pathlib import Path

from regista_core.config import Settings
from regista_core.telemetry import JsonFormatter

ENV_EXAMPLE = Path(__file__).resolve().parents[3] / ".env.example"
OFFLINE = {"bus": "memory", "llm_mode": "template", "tts_mode": "off", "store": "local"}


def _env_example_keys() -> set[str]:
    lines = ENV_EXAMPLE.read_text(encoding="utf-8").splitlines()
    return {
        line.split("=", 1)[0].strip()
        for line in lines
        if "=" in line and not line.lstrip().startswith("#")
    }


def test_code_defaults_run_offline(offline_settings):
    assert offline_settings.runtime_modes().model_dump() == OFFLINE


def test_env_example_parses_to_offline_defaults_with_empty_keys_unset():
    settings = Settings(_env_file=ENV_EXAMPLE)

    assert settings.runtime_modes().model_dump() == OFFLINE
    # `KEY=   # comment` must mean "unset", or Entra auth would think a key was configured.
    assert settings.foundry_project_endpoint is None
    assert settings.azure_openai_api_key is None
    assert settings.cors_origins == ["http://localhost:5173"]


def test_env_example_and_settings_list_the_same_keys():
    keys = _env_example_keys()
    web_only = {key for key in keys if key.startswith("VITE_")}
    fields = {name.upper() for name in Settings.model_fields}

    assert keys - web_only - fields == set(), "documented in .env.example but unused by the core"
    assert fields - keys == set(), "read by the core but missing from .env.example"


def test_cors_origins_accept_a_comma_separated_list(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:5173, https://regista.example")

    assert Settings(_env_file=None).cors_origins == [
        "http://localhost:5173",
        "https://regista.example",
    ]


def test_json_formatter_writes_one_utc_json_object_with_extras():
    record = logging.makeLogRecord(
        {"name": "regista", "levelname": "INFO", "msg": "kick off %s", "args": ("m001",)}
    )
    record.match_id = "m001"

    payload = json.loads(JsonFormatter().format(record))

    assert payload["message"] == "kick off m001"
    assert payload["match_id"] == "m001"
    assert payload["level"] == "INFO"
    assert payload["ts"].endswith("Z")
