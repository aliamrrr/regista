"""Structured JSON logging. OpenTelemetry export to Application Insights arrives in Phase 7."""

import json
import logging
import logging.config
from datetime import UTC, datetime
from typing import Any

# Attributes every LogRecord has; anything else on a record came from `extra=` and is logged.
# uvicorn adds `color_message` (an ANSI-coloured duplicate of the message): drop it too.
_STANDARD_ATTRS = frozenset(vars(logging.makeLogRecord({}))) | {
    "message",
    "asctime",
    "color_message",
}


class JsonFormatter(logging.Formatter):
    """Render each log record as one JSON object on one line, with a UTC timestamp."""

    def format(self, record: logging.LogRecord) -> str:
        """Return the JSON line for ``record``, including any ``extra=`` fields."""
        timestamp = datetime.fromtimestamp(record.created, tz=UTC)
        payload: dict[str, Any] = {
            "ts": timestamp.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        payload.update(
            (key, value) for key, value in vars(record).items() if key not in _STANDARD_ATTRS
        )
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        if record.stack_info:
            payload["stack_info"] = self.formatStack(record.stack_info)
        return json.dumps(payload, default=str, ensure_ascii=False)


def logging_config(level: str = "INFO") -> dict[str, Any]:
    """Return a ``dictConfig`` mapping that sends every logger, uvicorn's included, to JSON."""
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {"json": {"()": "regista_core.telemetry.JsonFormatter"}},
        "handlers": {
            "stderr": {
                "class": "logging.StreamHandler",
                "formatter": "json",
                "stream": "ext://sys.stderr",
            }
        },
        "root": {"handlers": ["stderr"], "level": level},
        "loggers": {
            name: {"handlers": [], "propagate": True}
            for name in ("uvicorn", "uvicorn.error", "uvicorn.access")
        },
    }


def configure_logging(level: str = "INFO") -> None:
    """Configure process-wide structured JSON logging at ``level``."""
    logging.config.dictConfig(logging_config(level))
