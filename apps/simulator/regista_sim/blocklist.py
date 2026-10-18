"""Real-name blocklist (docs/DATA_AND_METRICS.md §1, docs/SPEC.md §11).

The list covers real top-flight club names, the place names inside them and their usual
three-letter codes, plus well-known footballers' full names and distinctive surnames. It is
stored as truncated SHA-256 digests of normalized names, so the repository never contains the
real names themselves (CLAUDE.md: no real names anywhere, test fixtures included).

Add an entry by appending the output of
``uv run python -c "from regista_sim.blocklist import digest; print(digest('Some Name'))"``
to ``regista_sim/data/blocklist.sha256``.
"""

import hashlib
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

BLOCKLIST_PATH = Path(__file__).parent / "data" / "blocklist.sha256"
DIGEST_HEX_CHARS = 20  # 80 bits: no accidental collisions at this list size

# Letters that NFKD does not decompose into a base letter plus a combining mark.
_FOLD = str.maketrans(
    {"ø": "o", "æ": "ae", "œ": "oe", "ł": "l", "đ": "d", "ð": "d", "þ": "th", "ı": "i"}
)
_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def normalize(name: str) -> str:
    """Fold case, accents and punctuation: ``"Ñúñez-Ödegård"`` → ``"nunez odegard"``."""
    decomposed = unicodedata.normalize("NFKD", name.casefold().translate(_FOLD))
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return _NON_ALNUM.sub(" ", stripped).strip()


def digest(name: str) -> str:
    """Return the blocklist digest of ``name`` (truncated SHA-256 of its normalized form)."""
    return hashlib.sha256(normalize(name).encode()).hexdigest()[:DIGEST_HEX_CHARS]


@lru_cache(maxsize=1)
def blocked_digests() -> frozenset[str]:
    """Return every digest in the blocklist file (comment lines start with ``#``)."""
    lines = BLOCKLIST_PATH.read_text(encoding="utf-8").splitlines()
    return frozenset(line.strip() for line in lines if line.strip() and not line.startswith("#"))


def is_blocked(name: str) -> bool:
    """Return True when ``name`` normalizes to a blocklisted real name."""
    return digest(name) in blocked_digests()
