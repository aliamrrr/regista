"""Command-line entry point for ``regista-sim``.

Phase 0 ships the entry point only; ``league generate``, ``match run`` and ``calibrate``
arrive in Phase 1 (docs/ROADMAP.md).
"""

import argparse
from collections.abc import Sequence

from regista_sim import __version__


def build_parser() -> argparse.ArgumentParser:
    """Build the ``regista-sim`` argument parser."""
    parser = argparse.ArgumentParser(
        prog="regista-sim",
        description="Synthetic football league and match engine for REGISTA.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI with ``argv`` (defaults to ``sys.argv``) and return the exit code."""
    parser = build_parser()
    parser.parse_args(argv)
    parser.print_help()
    return 0
