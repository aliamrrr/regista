"""Deterministic random streams: one seed, many independent named substreams.

Every consumer asks for its own stream by name (``stream(seed, "league", "players", "HMR")``), so
adding a new consumer never shifts the numbers another one draws. Names are hashed with CRC-32,
which is stable across platforms and Python runs (unlike ``hash()`` on strings).
"""

import zlib

import numpy as np


def stream(seed: int, *names: str | int) -> np.random.Generator:
    """Return a PCG64 generator keyed by ``seed`` and a path of stream names."""
    key = [seed & 0xFFFFFFFF, *(zlib.crc32(str(name).encode()) for name in names)]
    return np.random.Generator(np.random.PCG64(np.random.SeedSequence(key)))
