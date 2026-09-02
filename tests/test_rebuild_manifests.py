"""Tests for jasentool.rebuild_manifests (rebuild-manifests subcommand)."""
import logging
import types

import pytest
import yaml

from jasentool.database import Database
from jasentool.rebuild_manifests import RebuildManifests


class FakeMongo:
    """Stands in for Database.find: samples by (profile, sample_id), groups verbatim."""

    def __init__(self, samples, groups=None):
        self.samples = samples
        self.groups = groups or []

    def find(self, collection, query, fields):  # noqa: ARG002 (fields unused, matches Database.find signature)
        if collection == "sample_group":
            return self.groups
        wanted_profile = query["pipeline.analysis_profile"]
        results = [s for s in self.samples if wanted_profile in s["pipeline"]["analysis_profile"]]
        if "sample_id" in query:
            results = [s for s in results if s.get("sample_id") == query["sample_id"]]
        return results


def _sample(sample_id, profile, sample_name="", lims_id=None):
    return {
        "sample_id": sample_id, "sample_name": sample_name, "lims_id": lims_id,
        "pipeline": {"analysis_profile": [profile]},
    }


def _make_options(tmp_path, backup_dir, profile="staphylococcus_aureus",
                  sample_id=None, no_bonsai=False):
    return types.SimpleNamespace(
        profile=profile, backup_dir=str(backup_dir), output_dir=str(tmp_path / "out"),
        db_name="db", db_collection="samples", db_collection_groups="sample_group",
        address="mongodb://localhost:27017/", no_bonsai=no_bonsai, sample_id=sample_id,
    )


def _touch(backup_dir, species, dirname, filename, content=""):
    d = backup_dir / species / dirname
    d.mkdir(parents=True, exist_ok=True)
    path = d / filename
    path.write_text(content)
    return path


@pytest.fixture()
def backup_dir(tmp_path):
    return tmp_path / "backup"


def _patch_database(monkeypatch, fake):
    monkeypatch.setattr(Database, "initialize", lambda *a, **kw: None)
    monkeypatch.setattr(Database, "find", fake.find)


# ── happy path ──────────────────────────────────────────────────────────────────

def test_writes_manifest_and_merged_versions(tmp_path, backup_dir, monkeypatch):
    species = "saureus"
    sample_id = "sample1"
    quast_path = _touch(backup_dir, species, "quast", f"{sample_id}_quast.tsv")
    sourmash_path = _touch(backup_dir, species, "sourmash", f"{sample_id}.sig")
    _touch(backup_dir, species, "chewbbaca", f"{sample_id}_chewbbaca.tsv")
    _touch(backup_dir, species, "mlst", f"{sample_id}_mlst.json")
    _touch(
        backup_dir, species, "quast", f"{sample_id}_ASSEMBLY_quast_versions.yml",
        "ASSEMBLY:quast:\n quast:\n  version: 5.2.0\n",
    )
    _touch(
        backup_dir, species, "chewbbaca", f"{sample_id}_TYPING_chewbbaca_versions.yml",
        "TYPING:chewbbaca:\n chewbbaca:\n  version: 3.5.2\n",
    )

    fake = FakeMongo(
        samples=[_sample(sample_id, "staphylococcus_aureus", sample_name="Sample One", lims_id="LIMS1")],
        groups=[{"name": "wgs", "included_samples": [sample_id]}],
    )
    _patch_database(monkeypatch, fake)

    options = _make_options(tmp_path, backup_dir)
    RebuildManifests(options).run()

    out_dir = tmp_path / "out"
    manifest = yaml.safe_load((out_dir / f"{sample_id}_bonsai.yaml").read_text())
    assert manifest["sample_id"] == sample_id
    assert manifest["sample_name"] == "Sample One"
    assert manifest["lims_id"] == "LIMS1"
    assert manifest["groups"] == ["wgs"]

    results = {e["software"]: e for e in manifest["analysis_result"]}
    assert results["quast"]["uri"] == str(quast_path)
    assert results["quast"]["software_version"] == "5.2.0"
    assert results["chewbbaca"]["software_version"] == "3.5.2"
    assert "software_version" not in results["mlst"]  # no version file backed up for mlst
    assert manifest["index_artifacts"]["sourmash_signature"] == str(sourmash_path)

    versions = yaml.safe_load((out_dir / f"{sample_id}_versions.yml").read_text())
    assert versions["ASSEMBLY:quast"]["quast"]["version"] == "5.2.0"
    assert versions["TYPING:chewbbaca"]["chewbbaca"]["version"] == "3.5.2"


def test_malformed_versions_file_is_skipped_not_fatal(tmp_path, backup_dir, monkeypatch, caplog):
    """A single unparseable _versions.yml is warned about and skipped; the good ones still merge."""
    species = "saureus"
    sample_id = "sample1"
    _touch(backup_dir, species, "quast", f"{sample_id}_quast.tsv")
    _touch(
        backup_dir, species, "quast", f"{sample_id}_ASSEMBLY_quast_versions.yml",
        "ASSEMBLY:quast:\n quast:\n  version: 5.2.0\n",
    )
    # Mimic a real broken file: a colon-bearing scalar that isn't a valid mapping key.
    _touch(
        backup_dir, species, "resfinder", f"{sample_id}_SCREENING:resfinder_versions.yml",
        "SCREENING:resfinder:\n resfinder:\n  version: 4.7.2\n bad line without colon\n  oops\n",
    )

    fake = FakeMongo(
        samples=[_sample(sample_id, "staphylococcus_aureus")],
        groups=[{"name": "wgs", "included_samples": [sample_id]}],
    )
    _patch_database(monkeypatch, fake)

    with caplog.at_level(logging.WARNING):
        RebuildManifests(_make_options(tmp_path, backup_dir)).run()

    out_dir = tmp_path / "out"
    # the run completed and the good version file still made it into the merge
    versions = yaml.safe_load((out_dir / f"{sample_id}_versions.yml").read_text())
    assert versions["ASSEMBLY:quast"]["quast"]["version"] == "5.2.0"
    assert "resfinder" not in versions
    assert "Skipping unparseable versions file" in caplog.text
    manifest = yaml.safe_load((out_dir / f"{sample_id}_bonsai.yaml").read_text())
    results = {e["software"]: e for e in manifest["analysis_result"]}
    assert results["quast"]["software_version"] == "5.2.0"


def test_versions_file_with_end_versions_sentinel_is_salvaged(tmp_path, backup_dir, monkeypatch):
    """A leaked `END_VERSIONS` heredoc terminator is stripped so the version is still captured."""
    species = "saureus"
    sample_id = "sample1"
    _touch(backup_dir, species, "resfinder", f"{sample_id}_resfinder.json")
    # Real JASEN shape: space-indented body plus a leaked END_VERSIONS delimiter line.
    _touch(
        backup_dir, species, "resfinder",
        f"{sample_id}_CALL_BACTERIAL_GENERAL:CALL_SCREENING:resfinder_versions.yml",
        "    CALL_BACTERIAL_GENERAL:CALL_SCREENING:resfinder:\n"
        "     resfinder:\n"
        "      version: 4.6.0\n"
        "      container: /fs1/resources/containers/resfinder.sif\n"
        "     resfinder_db:\n"
        "      version:\n"
        "      container: /fs1/resources/containers/resfinder.sif\n"
        "    END_VERSIONS\n",
    )

    fake = FakeMongo(
        samples=[_sample(sample_id, "staphylococcus_aureus")],
        groups=[{"name": "wgs", "included_samples": [sample_id]}],
    )
    _patch_database(monkeypatch, fake)

    RebuildManifests(_make_options(tmp_path, backup_dir)).run()

    out_dir = tmp_path / "out"
    versions = yaml.safe_load((out_dir / f"{sample_id}_versions.yml").read_text())
    assert versions["CALL_BACTERIAL_GENERAL:CALL_SCREENING:resfinder"]["resfinder"]["version"] == "4.6.0"
    manifest = yaml.safe_load((out_dir / f"{sample_id}_bonsai.yaml").read_text())
    results = {e["software"]: e for e in manifest["analysis_result"]}
    assert results["resfinder"]["software_version"] == "4.6.0"


def test_skips_outputs_with_no_create_yaml_field(tmp_path, backup_dir, monkeypatch):
    """resfinder_meta/mask_polymorph/format_jasen/save_analysis_metadata must not appear."""
    species = "saureus"
    sample_id = "sample1"
    _touch(backup_dir, species, "quast", f"{sample_id}_quast.tsv")
    _touch(backup_dir, species, "resfinder", f"{sample_id}_resfinder_meta.json")
    _touch(backup_dir, species, "mask", f"{sample_id}_mask.fasta")
    _touch(backup_dir, species, "analysis_result", f"{sample_id}_result.json")
    _touch(backup_dir, species, "analysis_metadata", f"{sample_id}_analysis_meta.json")

    fake = FakeMongo(samples=[_sample(sample_id, "staphylococcus_aureus")])
    _patch_database(monkeypatch, fake)

    RebuildManifests(_make_options(tmp_path, backup_dir)).run()

    manifest = yaml.safe_load((tmp_path / "out" / f"{sample_id}_bonsai.yaml").read_text())
    software_names = {e["software"] for e in manifest["analysis_result"]}
    assert software_names == {"quast"}


# ── --sample-id filtering ──────────────────────────────────────────────────────

def test_sample_id_filters_to_one_sample(tmp_path, backup_dir, monkeypatch):
    species = "saureus"
    for sid in ("sample1", "sample2"):
        _touch(backup_dir, species, "quast", f"{sid}_quast.tsv")

    fake = FakeMongo(samples=[
        _sample("sample1", "staphylococcus_aureus"),
        _sample("sample2", "staphylococcus_aureus"),
    ])
    _patch_database(monkeypatch, fake)

    options = _make_options(tmp_path, backup_dir, sample_id="sample2")
    RebuildManifests(options).run()

    out_dir = tmp_path / "out"
    assert not (out_dir / "sample1_bonsai.yaml").exists()
    assert (out_dir / "sample2_bonsai.yaml").exists()


def test_unknown_sample_id_writes_nothing(tmp_path, backup_dir, monkeypatch, caplog):
    fake = FakeMongo(samples=[_sample("sample1", "staphylococcus_aureus")])
    _patch_database(monkeypatch, fake)

    options = _make_options(tmp_path, backup_dir, sample_id="does-not-exist")
    with caplog.at_level(logging.ERROR):
        RebuildManifests(options).run()

    assert not (tmp_path / "out").exists()
    assert "does-not-exist" in caplog.text


# ── missing files degrade gracefully ───────────────────────────────────────────

def test_sample_with_no_backed_up_files_still_writes_minimal_manifest(tmp_path, backup_dir, monkeypatch, caplog):
    sample_id = "sample1"
    fake = FakeMongo(samples=[_sample(sample_id, "staphylococcus_aureus", sample_name="Sample One")])
    _patch_database(monkeypatch, fake)

    with caplog.at_level(logging.WARNING):
        RebuildManifests(_make_options(tmp_path, backup_dir)).run()

    out_dir = tmp_path / "out"
    manifest = yaml.safe_load((out_dir / f"{sample_id}_bonsai.yaml").read_text())
    assert manifest["analysis_result"] == []
    assert not (out_dir / f"{sample_id}_versions.yml").exists()
    assert "no analysis-result files found" in caplog.text
    assert "no per-process _versions.yml files found" in caplog.text


# ── TB vcf priority (tbprofiler_vcf > snippy_vcf) ──────────────────────────────

def test_tb_prefers_tbprofiler_vcf_over_snippy(tmp_path, backup_dir, monkeypatch):
    species = "mtuberculosis"
    sample_id = "sample1"
    tbprofiler_vcf = _touch(backup_dir, species, "vcf", f"{sample_id}_tbprofiler.vcf.gz")
    _touch(backup_dir, species, "snippy", f"{sample_id}_snippy.vcf")

    fake = FakeMongo(samples=[_sample(sample_id, "mycobacterium_tuberculosis")])
    _patch_database(monkeypatch, fake)

    options = _make_options(tmp_path, backup_dir, profile="mycobacterium_tuberculosis")
    RebuildManifests(options).run()

    manifest = yaml.safe_load((tmp_path / "out" / f"{sample_id}_bonsai.yaml").read_text())
    variants = next(e for e in manifest["igv_annotations"] if e["name"] == "Predicted variants")
    assert variants["uri"] == str(tbprofiler_vcf)


def test_tb_falls_back_to_snippy_vcf_when_tbprofiler_vcf_missing(tmp_path, backup_dir, monkeypatch):
    species = "mtuberculosis"
    sample_id = "sample1"
    snippy_vcf = _touch(backup_dir, species, "snippy", f"{sample_id}_snippy.vcf")

    fake = FakeMongo(samples=[_sample(sample_id, "mycobacterium_tuberculosis")])
    _patch_database(monkeypatch, fake)

    options = _make_options(tmp_path, backup_dir, profile="mycobacterium_tuberculosis")
    RebuildManifests(options).run()

    manifest = yaml.safe_load((tmp_path / "out" / f"{sample_id}_bonsai.yaml").read_text())
    variants = next(e for e in manifest["igv_annotations"] if e["name"] == "Predicted variants")
    assert variants["uri"] == str(snippy_vcf)


def test_tb_bam_and_bai_resolved(tmp_path, backup_dir, monkeypatch):
    species = "mtuberculosis"
    sample_id = "sample1"
    bam_path = _touch(backup_dir, species, "bam", f"{sample_id}_tbprofiler.bam")
    bai_path = _touch(backup_dir, species, "bam", f"{sample_id}_tbprofiler.bam.bai")

    fake = FakeMongo(samples=[_sample(sample_id, "mycobacterium_tuberculosis")])
    _patch_database(monkeypatch, fake)

    options = _make_options(tmp_path, backup_dir, profile="mycobacterium_tuberculosis")
    RebuildManifests(options).run()

    manifest = yaml.safe_load((tmp_path / "out" / f"{sample_id}_bonsai.yaml").read_text())
    coverage = next(e for e in manifest["igv_annotations"] if e["name"] == "Read coverage")
    assert coverage["uri"] == str(bam_path)
    assert coverage["index_uri"] == str(bai_path)


# ── groups reverse lookup ──────────────────────────────────────────────────────

def test_groups_reverse_lookup_multiple_groups(tmp_path, backup_dir, monkeypatch):
    sample_id = "sample1"
    fake = FakeMongo(
        samples=[_sample(sample_id, "staphylococcus_aureus")],
        groups=[
            {"name": "wgs", "included_samples": [sample_id]},
            {"name": "outbreak_2026", "included_samples": [sample_id, "other_sample"]},
            {"name": "unrelated", "included_samples": ["other_sample"]},
        ],
    )
    _patch_database(monkeypatch, fake)

    RebuildManifests(_make_options(tmp_path, backup_dir)).run()

    manifest = yaml.safe_load((tmp_path / "out" / f"{sample_id}_bonsai.yaml").read_text())
    assert sorted(manifest["groups"]) == ["outbreak_2026", "wgs"]


def test_sample_in_no_groups_gets_empty_list(tmp_path, backup_dir, monkeypatch):
    sample_id = "sample1"
    fake = FakeMongo(samples=[_sample(sample_id, "staphylococcus_aureus")], groups=[])
    _patch_database(monkeypatch, fake)

    RebuildManifests(_make_options(tmp_path, backup_dir)).run()

    manifest = yaml.safe_load((tmp_path / "out" / f"{sample_id}_bonsai.yaml").read_text())
    assert manifest["groups"] == []


# ── --no-bonsai: discover samples from the tree, no Mongo ────────────────────────

def _forbid_database(monkeypatch):
    """Make any Database access raise, proving --no-bonsai never touches Mongo."""
    def _boom(*a, **kw):
        raise AssertionError("Database must not be accessed with --no-bonsai")
    monkeypatch.setattr(Database, "initialize", _boom)
    monkeypatch.setattr(Database, "find", _boom)


def test_no_bonsai_discovers_samples_from_tree(tmp_path, backup_dir, monkeypatch):
    species = "saureus"
    for sid in ("sampleA", "sample_with_underscores"):
        _touch(backup_dir, species, "quast", f"{sid}_quast.tsv")
        _touch(backup_dir, species, "sourmash", f"{sid}.sig")
        _touch(
            backup_dir, species, "quast", f"{sid}_ASSEMBLY_quast_versions.yml",
            "ASSEMBLY:quast:\n quast:\n  version: 5.2.0\n",
        )
    _forbid_database(monkeypatch)

    RebuildManifests(_make_options(tmp_path, backup_dir, no_bonsai=True)).run()

    out_dir = tmp_path / "out"
    for sid in ("sampleA", "sample_with_underscores"):
        manifest = yaml.safe_load((out_dir / f"{sid}_bonsai.yaml").read_text())
        assert manifest["sample_id"] == sid
        assert manifest["sample_name"] == sid       # falls back to sample_id
        assert "lims_id" not in manifest            # unset -> omitted
        assert manifest["groups"] == []             # no Bonsai group lookup
        results = {e["software"]: e for e in manifest["analysis_result"]}
        assert results["quast"]["software_version"] == "5.2.0"
        assert (out_dir / f"{sid}_versions.yml").exists()


def test_no_bonsai_sample_id_filters(tmp_path, backup_dir, monkeypatch):
    species = "saureus"
    for sid in ("sample1", "sample2"):
        _touch(backup_dir, species, "quast", f"{sid}_quast.tsv")
    _forbid_database(monkeypatch)

    options = _make_options(tmp_path, backup_dir, no_bonsai=True, sample_id="sample2")
    RebuildManifests(options).run()

    out_dir = tmp_path / "out"
    assert not (out_dir / "sample1_bonsai.yaml").exists()
    assert (out_dir / "sample2_bonsai.yaml").exists()


def test_no_bonsai_unknown_sample_id_writes_nothing(tmp_path, backup_dir, monkeypatch, caplog):
    _touch(backup_dir, "saureus", "quast", "sample1_quast.tsv")
    _forbid_database(monkeypatch)

    options = _make_options(tmp_path, backup_dir, no_bonsai=True, sample_id="nope")
    with caplog.at_level(logging.ERROR):
        RebuildManifests(options).run()

    assert not (tmp_path / "out").exists()
    assert "nope" in caplog.text


def test_no_bonsai_ignores_wildcard_and_versions_files(tmp_path, backup_dir, monkeypatch):
    """A stray _versions.yml alone must not manufacture a phantom sample."""
    species = "saureus"
    _touch(backup_dir, species, "quast", "realSample_quast.tsv")
    # a versions file whose prefix isn't otherwise present must be ignored
    _touch(
        backup_dir, species, "chewbbaca", "ghost_TYPING_chewbbaca_versions.yml",
        "TYPING:chewbbaca:\n chewbbaca:\n  version: 3.5.2\n",
    )
    _forbid_database(monkeypatch)

    RebuildManifests(_make_options(tmp_path, backup_dir, no_bonsai=True)).run()

    out_dir = tmp_path / "out"
    assert (out_dir / "realSample_bonsai.yaml").exists()
    assert not (out_dir / "ghost_bonsai.yaml").exists()
