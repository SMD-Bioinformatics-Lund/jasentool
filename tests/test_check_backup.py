"""Tests for jasentool.check_backup."""
import json
import types

from jasentool.check_backup import CheckBackup, _per_output_stats
from jasentool.config import get_profile, made_by_release


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


def _scan(backup_dir, sample_ids, profile="staphylococcus_aureus"):
    entry = get_profile(profile)
    options = types.SimpleNamespace(
        profile=profile, backup_dir=str(backup_dir), output_file="unused.csv",
    )
    check = CheckBackup(options)
    samples = [{"sample_id": sid} for sid in sample_ids]
    summary, missing = check.scan(samples, entry["outputs"], entry["species"])
    return check, {row["sample_id"]: row for row in summary}, missing


def _write_outputs(backup_dir, sample_id, release, profile="staphylococcus_aureus", skip=()):
    """Write every output `release` made for the sample, except those in `skip`."""
    entry = get_profile(profile)
    for output in entry["outputs"]:
        name = output["software_name"]
        if name in skip or not made_by_release(output, release):
            continue
        ext = output["file_ext"] if isinstance(output["file_ext"], str) else output["file_ext"][0]
        path = (backup_dir / entry["species"] / output["dirname"]
                / f"{sample_id}{output['mask'].replace('*', 'chr')}{ext}")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"version": release}) if release else "")


def test_outputs_newer_than_the_sample_release_are_not_checked(tmp_path):
    _write_outputs(tmp_path, "S1", "0.9.0")

    _, summary, missing = _scan(tmp_path, ["S1"])

    assert summary["S1"]["status"] == "PASS"
    assert summary["S1"]["jasen_release"] == "0.9.0"
    assert missing == []


def test_required_outputs_follow_the_sample_release(tmp_path):
    _write_outputs(tmp_path, "S1", "1.4.1", skip={"samtools_stats", "create_yaml"})
    _write_outputs(tmp_path, "S2", "1.3.0", skip={"post_align_qc"})

    _, summary, missing = _scan(tmp_path, ["S1", "S2"])

    assert summary["S1"]["status"] == summary["S2"]["status"] == "FAIL"
    assert sorted((m["sample_id"], m["software_name"]) for m in missing) == [
        ("S1", "create_yaml"), ("S1", "samtools_stats"), ("S2", "post_align_qc")]


def test_unknown_release_checks_only_outputs_every_release_made(tmp_path):
    _, summary, missing = _scan(tmp_path, ["S1"])

    names = {m["software_name"] for m in missing}
    assert summary["S1"]["jasen_release"] == ""
    assert "save_analysis_metadata" in names
    assert not names & {"ska", "gambitcore", "create_yaml", "create_yaml_bonsai",
                        "samtools_stats", "post_align_qc"}


def test_species_typing_is_optional(tmp_path):
    _write_outputs(tmp_path, "S1", "1.4.1", profile="escherichia_coli",
                   skip={"serotypefinder_json", "serotypefinder_meta", "shigatyper"})

    _, summary, missing = _scan(tmp_path, ["S1"], profile="escherichia_coli")

    assert summary["S1"]["status"] == "PASS"
    assert {m["required"] for m in missing} == {"False"}


def test_output_stats_count_only_samples_whose_release_made_it(tmp_path):
    _write_outputs(tmp_path, "S1", "0.9.0")
    _write_outputs(tmp_path, "S2", "1.4.1", skip={"ska"})

    check, _, missing = _scan(tmp_path, ["S1", "S2"])
    stats = {row["software_name"]: row for row in
             _per_output_stats(get_profile("staphylococcus_aureus")["outputs"], missing,
                               check.expected_counts)}

    assert (stats["ska"]["total_samples"], stats["ska"]["n_missing"]) == (1, 1)
    assert stats["quast"]["total_samples"] == 2
