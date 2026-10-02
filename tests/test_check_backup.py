"""Tests for jasentool.check_backup."""
import types

from jasentool.check_backup import CheckBackup
from jasentool.config import get_profile


def _orphan_names(backup_dir, sample_ids, profile="staphylococcus_aureus"):
    entry = get_profile(profile)
    options = types.SimpleNamespace(
        profile=profile, backup_dir=str(backup_dir), output_file="unused.csv",
    )
    orphans = CheckBackup(options).find_orphans(sample_ids, entry["outputs"], entry["species"])
    return {orphan["filename"] for orphan in orphans}


def test_bracken_report_in_kraken_dir_is_not_an_orphan(tmp_path):
    kraken = tmp_path / "saureus" / "kraken"
    kraken.mkdir(parents=True)
    for name in ("S1_bracken.out", "S1_bracken.report", "S2_bracken.report"):
        (kraken / name).write_text("")

    # S2 isn't a known sample, so its report is still an orphan
    assert _orphan_names(tmp_path, ["S1"]) == {"S2_bracken.report"}
