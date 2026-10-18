"""The committed dataset: every file under the pre-commit size limit, the expected files present."""

from sim_helpers import DATA

LIMIT_KB = 1024  # .pre-commit-config.yaml: check-added-large-files --maxkb=1024


def test_every_committed_data_file_is_under_the_hook_limit():
    too_big = [
        (str(p.relative_to(DATA)), p.stat().st_size // 1024)
        for p in DATA.rglob("*")
        if p.is_file()
        and p.name not in ("events.jsonl", "tracking.jsonl.gz")
        and p.stat().st_size > LIMIT_KB * 1024
    ]
    assert too_big == []


def test_dataset_layout():
    golden = {p.name for p in (DATA / "golden").iterdir()}
    assert {
        "metadata.json",
        "events.jsonl.gz",
        "tracking.npz",
        "ground_truth.json",
        "summary.json",
    } <= golden
    league = {p.name for p in (DATA / "league").iterdir()}
    assert league == {
        "league.json",
        "clubs.json",
        "players.json",
        "careers.json",
        "match_logs.json",
    }
    assert (DATA / "DATA_CARD.md").exists()
