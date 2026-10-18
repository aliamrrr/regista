"""Deterministic JSON writers: UTF-8, LF line endings, stable key order."""

import gzip
import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any


def dumps_compact(obj: Any) -> str:
    """Return ``obj`` as compact one-line JSON (no spaces, non-ASCII kept)."""
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def write_pretty(path: Path, obj: Any) -> None:
    """Write ``obj`` as indented JSON (for small, human-read files)."""
    text = json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False)
    path.write_text(text + "\n", encoding="utf-8", newline="\n")


def write_array_lines(path: Path, items: Iterable[Any]) -> None:
    """Write a JSON array with one compact element per line (small diffs, small files)."""
    body = ",\n".join(dumps_compact(item) for item in items)
    path.write_text(f"[\n{body}\n]\n", encoding="utf-8", newline="\n")


def write_jsonl(path: Path, items: Iterable[Any]) -> None:
    """Write JSON Lines: one compact object per line."""
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for item in items:
            handle.write(dumps_compact(item))
            handle.write("\n")


def write_jsonl_gz_copy(source: Path, target: Path) -> None:
    """Gzip ``source`` to ``target`` without a file name or timestamp (byte-stable)."""
    with (
        target.open("wb") as raw,
        gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0, compresslevel=9) as handle,
    ):
        handle.write(source.read_bytes())


def read_jsonl(path: Path) -> list[Any]:
    """Read JSON Lines from ``path`` (``.jsonl`` or ``.jsonl.gz``)."""
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            return [json.loads(line) for line in handle if line.strip()]
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def read_json(path: Path) -> Any:
    """Read a JSON file."""
    return json.loads(path.read_text(encoding="utf-8"))
