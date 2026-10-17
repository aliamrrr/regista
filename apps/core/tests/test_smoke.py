"""Smoke tests: the service boots offline and answers its system endpoints."""

import pytest
from fastapi.testclient import TestClient

from regista_core import __version__
from regista_core.app import create_app
from regista_core.cli import main


@pytest.fixture
def client(offline_settings):
    with TestClient(create_app(offline_settings)) as test_client:
        yield test_client


def test_healthz_is_ok(client):
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_version_reports_the_package_version_and_offline_modes(client):
    response = client.get("/api/version")

    assert response.status_code == 200
    assert response.json() == {
        "name": "regista-core",
        "version": __version__,
        "modes": {"bus": "memory", "llm_mode": "template", "tts_mode": "off", "store": "local"},
    }


def test_cors_allows_the_local_web_origin_only(client):
    allowed = client.get("/healthz", headers={"Origin": "http://localhost:5173"})
    other = client.get("/healthz", headers={"Origin": "https://elsewhere.example"})

    assert allowed.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert "access-control-allow-origin" not in other.headers


def test_cli_prints_its_version(capsys):
    with pytest.raises(SystemExit) as exit_info:
        main(["--version"])

    assert exit_info.value.code == 0
    assert capsys.readouterr().out.strip() == f"regista-core {__version__}"
