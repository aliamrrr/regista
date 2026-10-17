"""Command-line entry point for ``regista-core``.

Phase 0 ships ``serve``; ``analyze <match_dir>`` arrives with the analytics engine in Phase 2.
"""

import argparse
from collections.abc import Sequence

import uvicorn

from regista_core import __version__
from regista_core.config import get_settings
from regista_core.telemetry import logging_config


def build_parser() -> argparse.ArgumentParser:
    """Build the ``regista-core`` argument parser."""
    parser = argparse.ArgumentParser(prog="regista-core", description="REGISTA core service.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")

    serve = commands.add_parser("serve", help="run the API + WebSocket service")
    serve.add_argument("--host", default="127.0.0.1", help="bind address (default: %(default)s)")
    serve.add_argument("--port", type=int, default=8000, help="port (default: %(default)s)")
    serve.add_argument("--reload", action="store_true", help="restart on code changes (dev only)")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI with ``argv`` (defaults to ``sys.argv``) and return the exit code."""
    args = build_parser().parse_args(argv)
    if args.command == "serve":
        uvicorn.run(
            "regista_core.app:create_app",
            factory=True,
            host=args.host,
            port=args.port,
            reload=args.reload,
            log_config=logging_config(get_settings().log_level),
        )
    return 0
