"""Smoke test: the simulator package imports and its CLI answers ``--version``."""

from importlib.metadata import version

import pytest

import regista_sim
from regista_sim.cli import main


def test_package_version_comes_from_the_installed_metadata():
    assert regista_sim.__version__ == version("regista-sim")


def test_cli_prints_its_version(capsys):
    with pytest.raises(SystemExit) as exit_info:
        main(["--version"])

    assert exit_info.value.code == 0
    assert capsys.readouterr().out.strip() == f"regista-sim {regista_sim.__version__}"
