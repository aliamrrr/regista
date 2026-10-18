"""Synthetic only: no real club, stadium or footballer name anywhere (SPEC §11, CLAUDE.md rule 4).

The blocklist stores digests, so neither the code nor these tests contain a real name.
"""

import re

from regista_sim import blocklist
from regista_sim.blocklist import BLOCKLIST_PATH, blocked_digests, digest, is_blocked, normalize


def _all_names(league) -> list[str]:
    names = [league.name]
    for club in league.clubs:
        names += [club.name, club.short_name, club.venue, club.code]
    for player in league.players:
        names += [player.name, player.last_name]
    names += [r.name for r in league.referees]
    names += [r.name.split()[-1] for r in league.referees]
    return names


def test_no_generated_name_is_on_the_blocklist(league):
    hits = [name for name in _all_names(league) if is_blocked(name)]
    assert hits == []


def test_blocklist_file_holds_only_digests():
    lines = [
        ln
        for ln in BLOCKLIST_PATH.read_text(encoding="utf-8").splitlines()
        if ln and not ln.startswith("#")
    ]
    assert len(lines) >= 1000
    assert all(re.fullmatch(r"[0-9a-f]{20}", ln) for ln in lines)
    assert len(set(lines)) == len(lines)


def test_normalize_folds_case_accents_and_punctuation():
    assert normalize("  Ñóvak-Strånd  ") == "novak strand"
    assert normalize("Ødegård O'Hare") == "odegard o hare"
    assert digest("ZEPHYR quillon") == digest("Zéphyr  Quillon!")


def test_a_listed_name_is_caught(monkeypatch):
    invented = "Zorbatt Quillenmoor"  # invented: stands in for a real name in this test
    assert not is_blocked(invented)
    monkeypatch.setattr(blocklist, "blocked_digests", lambda: frozenset({digest(invented)}))
    assert blocklist.is_blocked("zorbatt  QUILLENMOOR")
    blocked_digests.cache_clear()
