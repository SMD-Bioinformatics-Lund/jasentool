"""Tests for jasentool.rebuild_manifests (rebuild-manifests subcommand)."""
import csv
import json
import logging
import os
import types
from pathlib import Path

import pytest
import yaml

from jasentool.config import CREATE_YAML_VCF_PRIORITY, get_profile, made_by_release
from jasentool.database import Database
from jasentool.rebuild_manifests import _MANIFEST_SOFTWARE, FAILED_FILENAME, RebuildManifests


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
                  sample_id=None, no_bonsai=False, jasen_version=None,
                  reference_genome_accession=None, symlink_dir=None, force=False,
                  assets_dir=None):
    return types.SimpleNamespace(
        profile=profile, backup_dir=str(backup_dir), output_dir=str(tmp_path / "out"),
        db_name="db", db_collection="samples", db_collection_groups="sample_group",
        address="mongodb://localhost:27017/", no_bonsai=no_bonsai, sample_id=sample_id,
        jasen_version=jasen_version, reference_genome_accession=reference_genome_accession,
        symlink_dir=None if symlink_dir is None else str(symlink_dir), force=force,
        assets_dir=None if assets_dir is None else str(assets_dir),
    )


def _touch(backup_dir, species, dirname, filename, content=""):
    d = backup_dir / species / dirname
    d.mkdir(parents=True, exist_ok=True)
    path = d / filename
    path.write_text(content)
    return path


def _add_missing_required_outputs(rebuild, sample_ids):
    """Create the required manifest inputs a test left out, so its sample isn't failed.

    Only outputs the sample's JASEN release made are added. Files a test made are kept;
    the vcf slot is filled only when no vcf source exists.
    """
    profile = get_profile(rebuild.profile)
    species = profile["species"]
    for sample_id in sample_ids:
        _, metadata = rebuild._resolve_run_metadata(profile["outputs"], species, sample_id)
        release = rebuild.jasen_version or metadata.get("version")
        missing = []
        has_vcf = False
        for output in profile["outputs"]:
            name = output["software_name"]
            if name not in _MANIFEST_SOFTWARE:
                continue
            root, dirname = rebuild._search_location(output)
            if rebuild._resolve_output_path(output, species, sample_id, root=root, dirname=dirname):
                has_vcf = has_vcf or name in CREATE_YAML_VCF_PRIORITY
            elif output["required"] and made_by_release(output, release):
                missing.append((output, root, dirname))
        for output, root, dirname in missing:
            if has_vcf and output["software_name"] in CREATE_YAML_VCF_PRIORITY:
                continue
            ext = output["file_ext"] if isinstance(output["file_ext"], str) else output["file_ext"][0]
            path = Path(root) / species / dirname / f"{sample_id}{output['mask']}{ext}"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("{}" if ext == ".json" else "")
            has_vcf = has_vcf or output["software_name"] in CREATE_YAML_VCF_PRIORITY


def _rebuild(options):
    """Run rebuild-manifests after adding any required inputs the test didn't create."""
    rebuild = RebuildManifests(options)
    profile = get_profile(options.profile)
    if options.no_bonsai:
        samples = rebuild._discover_samples_from_tree(profile["outputs"], profile["species"])
    else:
        samples = rebuild._fetch_bonsai_samples()
    _add_missing_required_outputs(rebuild, [s["sample_id"] for s in samples])
    rebuild.run()


@pytest.fixture()
def backup_dir(tmp_path):
    return tmp_path / "backup"


def _patch_database(monkeypatch, fake):
    monkeypatch.setattr(Database, "initialize", lambda *a, **kw: None)
    monkeypatch.setattr(Database, "find", fake.find)
    monkeypatch.setattr(Database, "require_collection", lambda *a, **kw: None)


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
    _rebuild(options)

    out_dir = tmp_path / "out"
    manifest = yaml.safe_load((out_dir / f"{sample_id}_bonsai.yaml").read_text())
    assert manifest["sample_id"] == sample_id
    assert manifest["sample_name"] == "Sample One"
    assert manifest["lims_id"] == "LIMS1"
    assert manifest["groups"] == ["saureus", "wgs"]

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
    # Broken beyond the colon-less-junk salvage: tab indentation is never valid YAML.
    _touch(
        backup_dir, species, "resfinder", f"{sample_id}_SCREENING:resfinder_versions.yml",
        "SCREENING:resfinder:\n\tresfinder:\n\t\tversion: 4.7.2\n",
    )

    fake = FakeMongo(
        samples=[_sample(sample_id, "staphylococcus_aureus")],
        groups=[{"name": "wgs", "included_samples": [sample_id]}],
    )
    _patch_database(monkeypatch, fake)

    with caplog.at_level(logging.WARNING):
        _rebuild(_make_options(tmp_path, backup_dir))

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

    _rebuild(_make_options(tmp_path, backup_dir))

    out_dir = tmp_path / "out"
    versions = yaml.safe_load((out_dir / f"{sample_id}_versions.yml").read_text())
    assert versions["CALL_BACTERIAL_GENERAL:CALL_SCREENING:resfinder"]["resfinder"]["version"] == "4.6.0"
    manifest = yaml.safe_load((out_dir / f"{sample_id}_bonsai.yaml").read_text())
    results = {e["software"]: e for e in manifest["analysis_result"]}
    assert results["resfinder"]["software_version"] == "4.6.0"


def test_versions_file_with_stray_bare_version_line_is_salvaged(tmp_path, backup_dir, monkeypatch):
    """A duplicated bare version value on its own line is dropped so the version is captured."""
    species = "saureus"
    sample_id = "sample1"
    _touch(backup_dir, species, "spatyper", f"{sample_id}_spatyper.tsv")
    _touch(
        backup_dir, species, "spatyper",
        f"{sample_id}_CALL_BACTERIAL_GENERAL:CALL_TYPING:spatyper_versions.yml",
        "CALL_BACTERIAL_GENERAL:CALL_TYPING:spatyper:\n"
        " spatyper:\n"
        "  version: 0.2.1\n"
        "0.2.1\n"
        "  container: /fs1/resources/containers/spatyper.sif\n",
    )

    fake = FakeMongo(
        samples=[_sample(sample_id, "staphylococcus_aureus")],
        groups=[{"name": "wgs", "included_samples": [sample_id]}],
    )
    _patch_database(monkeypatch, fake)

    _rebuild(_make_options(tmp_path, backup_dir))

    out_dir = tmp_path / "out"
    versions = yaml.safe_load((out_dir / f"{sample_id}_versions.yml").read_text())
    assert versions["CALL_BACTERIAL_GENERAL:CALL_TYPING:spatyper"]["spatyper"]["version"] == "0.2.1"
    manifest = yaml.safe_load((out_dir / f"{sample_id}_bonsai.yaml").read_text())
    results = {e["software"]: e for e in manifest["analysis_result"]}
    assert results["spatyper"]["software_version"] == "0.2.1"


def test_versions_fallback_fills_missing_and_db_only(tmp_path, backup_dir, monkeypatch):
    """Fallback fills a tool with no versions.yml and one whose file only has a _db version."""
    species = "saureus"
    sample_id = "sample1"
    # chewbbaca: output present, no versions.yml at all
    _touch(backup_dir, species, "chewbbaca", f"{sample_id}_chewbbaca.tsv")
    # virulencefinder: output present, versions.yml has only the _db block
    _touch(backup_dir, species, "virulencefinder", f"{sample_id}_virulencefinder.json")
    _touch(
        backup_dir, species, "virulencefinder",
        f"{sample_id}_CALL_BACTERIAL_GENERAL:CALL_SCREENING:virulencefinder_versions.yml",
        "CALL_BACTERIAL_GENERAL:CALL_SCREENING:virulencefinder:\n"
        " virulencefinder_db:\n"
        "  version: 2.0.1\n"
        "END_VERSIONS\n",
    )
    # quast: real tree version -- must win over any fallback value
    _touch(backup_dir, species, "quast", f"{sample_id}_quast.tsv")
    _touch(
        backup_dir, species, "quast", f"{sample_id}_ASSEMBLY_quast_versions.yml",
        "ASSEMBLY:quast:\n quast:\n  version: 5.2.0\n",
    )

    monkeypatch.setattr(
        "jasentool.rebuild_manifests.VERSIONS_FALLBACK",
        {"test": {"chewbbaca": "3.3.2", "virulencefinder": "2.0.4", "quast": "9.9.9"}},
    )

    fake = FakeMongo(
        samples=[_sample(sample_id, "staphylococcus_aureus")],
        groups=[{"name": "wgs", "included_samples": [sample_id]}],
    )
    _patch_database(monkeypatch, fake)

    options = _make_options(tmp_path, backup_dir, jasen_version="test")
    _rebuild(options)

    manifest = yaml.safe_load((tmp_path / "out" / f"{sample_id}_bonsai.yaml").read_text())
    results = {e["software"]: e for e in manifest["analysis_result"]}
    assert results["chewbbaca"]["software_version"] == "3.3.2"      # filled (no file)
    assert results["virulencefinder"]["software_version"] == "2.0.4"  # filled (_db only)
    assert results["quast"]["software_version"] == "5.2.0"          # tree wins over fallback 9.9.9


@pytest.mark.parametrize("bad_version_line", ["  version: gambitcore\n", "  version:\n"])
def test_unusable_tree_version_replaced_by_fallback(tmp_path, backup_dir, monkeypatch,
                                                    bad_version_line):
    """gambitcore writes its own name as the version; sed -n can write an empty one."""
    species = "saureus"
    sample_id = "sample1"
    _touch(backup_dir, species, "gambitcore", f"{sample_id}_gambitcore.tsv")
    _touch(
        backup_dir, species, "gambitcore",
        f"{sample_id}_CALL_BACTERIAL_GENERAL:CALL_QUALITY_CONTROL:gambitcore_versions.yml",
        "CALL_BACTERIAL_GENERAL:CALL_QUALITY_CONTROL:gambitcore:\n"
        " gambitcore:\n"
        f"{bad_version_line}"
        "  container: /fs1/resources/containers/gambitcore.sif\n",
    )
    monkeypatch.setattr(
        "jasentool.rebuild_manifests.VERSIONS_FALLBACK", {"test": {"gambitcore": "0.0.2"}}
    )

    fake = FakeMongo(samples=[_sample(sample_id, "staphylococcus_aureus")])
    _patch_database(monkeypatch, fake)

    _rebuild(_make_options(tmp_path, backup_dir, jasen_version="test"))

    manifest = yaml.safe_load((tmp_path / "out" / f"{sample_id}_bonsai.yaml").read_text())
    results = {e["software"]: e for e in manifest["analysis_result"]}
    assert results["gambitcore"]["software_version"] == "0.0.2"
    versions_text = (tmp_path / "out" / f"{sample_id}_versions.yml").read_text()
    assert "CALL_QUALITY_CONTROL:gambitcore" not in versions_text


def test_unusable_tree_version_without_fallback_is_omitted(tmp_path, backup_dir, monkeypatch):
    """Without --jasen-version the junk version must not reach the manifest."""
    species = "saureus"
    sample_id = "sample1"
    _touch(backup_dir, species, "gambitcore", f"{sample_id}_gambitcore.tsv")
    _touch(
        backup_dir, species, "gambitcore", f"{sample_id}_QC:gambitcore_versions.yml",
        "QC:gambitcore:\n gambitcore:\n  version: gambitcore\n",
    )
    fake = FakeMongo(samples=[_sample(sample_id, "staphylococcus_aureus")])
    _patch_database(monkeypatch, fake)

    _rebuild(_make_options(tmp_path, backup_dir))

    manifest = yaml.safe_load((tmp_path / "out" / f"{sample_id}_bonsai.yaml").read_text())
    results = {e["software"]: e for e in manifest["analysis_result"]}
    assert "software_version" not in results["gambitcore"]


@pytest.mark.parametrize("jasen_version, chewbbaca_version",
                         [("0.8.0", "3.3.2"), ("0.9.0", "3.3.2"), ("1.1.0", "3.3.2"), ("1.3.0", "3.5.3")])
def test_versions_fallback_only_fills_relevant_software(tmp_path, backup_dir, monkeypatch,
                                                       jasen_version, chewbbaca_version):
    """--jasen-version fills from that release, and only for tools the sample has an output for."""
    species = "saureus"
    sample_id = "sample1"
    _touch(backup_dir, species, "chewbbaca", f"{sample_id}_chewbbaca.tsv")

    fake = FakeMongo(
        samples=[_sample(sample_id, "staphylococcus_aureus")],
        groups=[{"name": "wgs", "included_samples": [sample_id]}],
    )
    _patch_database(monkeypatch, fake)

    options = _make_options(tmp_path, backup_dir, jasen_version=jasen_version)
    _rebuild(options)

    versions = yaml.safe_load((tmp_path / "out" / f"{sample_id}_versions.yml").read_text())
    fallback_block = versions["jasentool_version_fallback"]
    assert fallback_block["chewbbaca"] == {"version": chewbbaca_version}
    # spades is in every release's map but isn't a create-yaml analysis tool
    assert "spades" not in fallback_block


def test_run_metadata_populates_nextflow_run_info_and_lims_id(tmp_path, backup_dir, monkeypatch):
    """analysis_meta.json supplies nextflow_run_info + lims_id (+ sample_name in no-bonsai)."""
    species = "saureus"
    sample_id = "MT220001"
    _touch(backup_dir, species, "quast", f"{sample_id}_quast.tsv")
    meta_path = _touch(
        backup_dir, species, "analysis_metadata", f"{sample_id}_analysis_meta.json",
        json.dumps({
            "sample_name": "MT220001",
            "lims_id": "CMD1111A222",
            "sequencing_run": "22MT0001",
            "pipeline": "main.nf",
            "version": "1.1.2",
        }),
    )

    fake = FakeMongo(
        samples=[_sample(sample_id, "staphylococcus_aureus")], groups=[],
    )
    _patch_database(monkeypatch, fake)

    # no-bonsai so name/lims_id come purely from the metadata JSON
    _rebuild(_make_options(tmp_path, backup_dir, no_bonsai=True))

    manifest = yaml.safe_load((tmp_path / "out" / f"{sample_id}_bonsai.yaml").read_text())
    assert manifest["lims_id"] == "CMD1111A222"
    assert manifest["sample_name"] == "MT220001"
    # nextflow_run_info points at the original backup-tree file; nothing is copied out
    assert manifest["nextflow_run_info"] == os.path.abspath(str(meta_path))
    assert not (tmp_path / "out" / f"{sample_id}_analysis_meta.json").exists()


def test_bonsai_lims_id_wins_over_metadata(tmp_path, backup_dir, monkeypatch):
    """Bonsai's lims_id/sample_name are authoritative; metadata only fills gaps."""
    species = "saureus"
    sample_id = "MT220001"
    _touch(backup_dir, species, "quast", f"{sample_id}_quast.tsv")
    meta_path = _touch(
        backup_dir, species, "analysis_metadata", f"{sample_id}_analysis_meta.json",
        json.dumps({"sample_name": "meta_name", "lims_id": "META_LIMS"}),
    )

    fake = FakeMongo(
        samples=[_sample(sample_id, "staphylococcus_aureus",
                         sample_name="Bonsai Name", lims_id="BONSAI_LIMS")],
        groups=[],
    )
    _patch_database(monkeypatch, fake)

    _rebuild(_make_options(tmp_path, backup_dir))

    manifest = yaml.safe_load((tmp_path / "out" / f"{sample_id}_bonsai.yaml").read_text())
    assert manifest["lims_id"] == "BONSAI_LIMS"
    assert manifest["sample_name"] == "Bonsai Name"
    # nextflow_run_info still points at the original backup-tree file (no Bonsai equivalent)
    assert manifest["nextflow_run_info"] == os.path.abspath(str(meta_path))


def test_reference_genome_accession_from_flag(tmp_path, backup_dir, monkeypatch):
    """rebuild-manifests stamps an explicit --reference-genome-accession onto the manifest."""
    species = "saureus"
    sample_id = "sample1"
    _touch(backup_dir, species, "quast", f"{sample_id}_quast.tsv")

    fake = FakeMongo(samples=[_sample(sample_id, "staphylococcus_aureus")], groups=[])
    _patch_database(monkeypatch, fake)

    options = _make_options(tmp_path, backup_dir, no_bonsai=True,
                            reference_genome_accession="GCF_000012045.1")
    _rebuild(options)

    manifest = yaml.safe_load((tmp_path / "out" / f"{sample_id}_bonsai.yaml").read_text())
    assert manifest["reference_genome_accession"] == "GCF_000012045.1"


def test_reference_genome_accession_omitted_when_not_provided(tmp_path, backup_dir, monkeypatch):
    """Without the flag, the manifest simply has no reference_genome_accession."""
    species = "saureus"
    sample_id = "sample1"
    _touch(backup_dir, species, "quast", f"{sample_id}_quast.tsv")

    fake = FakeMongo(samples=[_sample(sample_id, "staphylococcus_aureus")], groups=[])
    _patch_database(monkeypatch, fake)

    _rebuild(_make_options(tmp_path, backup_dir, no_bonsai=True))

    manifest = yaml.safe_load((tmp_path / "out" / f"{sample_id}_bonsai.yaml").read_text())
    assert "reference_genome_accession" not in manifest


def test_run_metadata_left_untouched(tmp_path, backup_dir, monkeypatch):
    """rebuild-manifests neither copies nor rewrites analysis_meta.json (e.g. release_life_cycle)."""
    species = "saureus"
    sample_id = "MT220001"
    _touch(backup_dir, species, "quast", f"{sample_id}_quast.tsv")
    meta_path = _touch(
        backup_dir, species, "analysis_metadata", f"{sample_id}_analysis_meta.json",
        json.dumps({"lims_id": "L1", "release_life_cycle": "diagnostic"}),
    )

    fake = FakeMongo(samples=[_sample(sample_id, "staphylococcus_aureus")], groups=[])
    _patch_database(monkeypatch, fake)

    _rebuild(_make_options(tmp_path, backup_dir, no_bonsai=True))

    manifest = yaml.safe_load((tmp_path / "out" / f"{sample_id}_bonsai.yaml").read_text())
    # manifest references the original file, which is left exactly as-is
    assert manifest["nextflow_run_info"] == os.path.abspath(str(meta_path))
    assert not (tmp_path / "out" / f"{sample_id}_analysis_meta.json").exists()
    assert json.loads(meta_path.read_text())["release_life_cycle"] == "diagnostic"


def test_skips_outputs_with_no_create_yaml_field(tmp_path, backup_dir, monkeypatch):
    """mask_polymorph/format_jasen/save_analysis_metadata must not appear as results."""
    species = "saureus"
    sample_id = "sample1"
    _touch(backup_dir, species, "quast", f"{sample_id}_quast.tsv")
    _touch(backup_dir, species, "resfinder", f"{sample_id}_resfinder_meta.json")
    _touch(backup_dir, species, "mask", f"{sample_id}_mask.fasta")
    _touch(backup_dir, species, "analysis_result", f"{sample_id}_result.json")
    _touch(backup_dir, species, "analysis_metadata", f"{sample_id}_analysis_meta.json", "{}")

    fake = FakeMongo(samples=[_sample(sample_id, "staphylococcus_aureus")])
    _patch_database(monkeypatch, fake)

    _rebuild(_make_options(tmp_path, backup_dir))

    manifest = yaml.safe_load((tmp_path / "out" / f"{sample_id}_bonsai.yaml").read_text())
    uris = [e["uri"] for e in manifest["analysis_result"]]
    assert any(uri.endswith("_quast.tsv") for uri in uris)
    assert not any(uri.endswith(("_mask.fasta", "_result.json", "_analysis_meta.json"))
                   for uri in uris)


def test_alignment_qc_outputs_resolved_with_subcommands(tmp_path, backup_dir, monkeypatch):
    """samtools coverage/stats/bedcov replace the retired postalignqc output."""
    species = "saureus"
    sample_id = "sample1"
    _touch(backup_dir, species, "coverage", f"{sample_id}_bwa_mapcoverage.txt")
    _touch(backup_dir, species, "samtools_stats", f"{sample_id}.stats")
    _touch(backup_dir, species, "samtools_bedcov", f"{sample_id}.bedcov.tsv")
    _touch(backup_dir, species, "analysis_metadata", f"{sample_id}_analysis_meta.json", "{}")

    fake = FakeMongo(samples=[_sample(sample_id, "staphylococcus_aureus")])
    _patch_database(monkeypatch, fake)

    _rebuild(_make_options(tmp_path, backup_dir))

    manifest = yaml.safe_load((tmp_path / "out" / f"{sample_id}_bonsai.yaml").read_text())
    entries = {
        (e["software"], e.get("subcommand")): e["uri"] for e in manifest["analysis_result"]
    }
    assert ("samtools", "coverage") in entries
    assert ("samtools", "stats") in entries
    assert ("samtools", "bedcov") in entries
    assert entries[("samtools", "stats")].endswith(f"{sample_id}.stats")
    assert entries[("samtools", "bedcov")].endswith(f"{sample_id}.bedcov.tsv")
    assert entries[("samtools", "coverage")].endswith("_mapcoverage.txt")


def test_klebsiella_profile_resolves_kleborate_and_serotypefinder(tmp_path, backup_dir,
                                                                   monkeypatch):
    species = "klebsiella"
    sample_id = "sample1"
    _touch(backup_dir, species, "kleborate", f"{sample_id}_kleborate.txt")
    _touch(backup_dir, species, "kleborate", f"{sample_id}_kleborate_hAMRonization.txt")
    _touch(backup_dir, species, "serotypefinder", f"{sample_id}_serotypefinder.json")
    _touch(backup_dir, species, "samtools_stats", f"{sample_id}.stats")

    fake = FakeMongo(samples=[_sample(sample_id, "klebsiella")])
    _patch_database(monkeypatch, fake)

    _rebuild(_make_options(tmp_path, backup_dir, profile="klebsiella"))

    manifest = yaml.safe_load((tmp_path / "out" / f"{sample_id}_bonsai.yaml").read_text())
    entries = {(e["software"], e.get("subcommand")) for e in manifest["analysis_result"]}
    assert ("kleborate", None) in entries
    assert ("hAMRonization", None) in entries
    assert ("serotypefinder", None) in entries
    assert ("samtools", "stats") in entries
    assert manifest["groups"] == ["klebsiella"]


def test_staphylococcus_profile_resolves_staph_typing(tmp_path, backup_dir, monkeypatch):
    species = "staphylococcus"
    sample_id = "sample1"
    _touch(backup_dir, species, "sccmec", f"{sample_id}_sccmec.tsv")
    _touch(backup_dir, species, "spatyper", f"{sample_id}_spatyper.tsv")
    _touch(backup_dir, species, "samtools_stats", f"{sample_id}.stats")

    fake = FakeMongo(samples=[_sample(sample_id, "staphylococcus")])
    _patch_database(monkeypatch, fake)

    _rebuild(_make_options(tmp_path, backup_dir, profile="staphylococcus"))

    manifest = yaml.safe_load((tmp_path / "out" / f"{sample_id}_bonsai.yaml").read_text())
    entries = {(e["software"], e.get("subcommand")) for e in manifest["analysis_result"]}
    assert ("sccmectyper", None) in entries
    assert ("spatyper", None) in entries
    assert ("samtools", "stats") in entries
    assert manifest["groups"] == ["staphylococcus"]


def test_alignment_qc_resolved_for_spyogenes(tmp_path, backup_dir, monkeypatch):
    """JASEN runs alignment QC for S. pyogenes; only the generic streptococcus profile skips it."""
    species = "spyogenes"
    sample_id = "sample1"
    _touch(backup_dir, species, "coverage", f"{sample_id}_bwa_mapcoverage.txt")
    _touch(backup_dir, species, "samtools_stats", f"{sample_id}.stats")
    _touch(backup_dir, species, "samtools_bedcov", f"{sample_id}.bedcov.tsv")

    fake = FakeMongo(samples=[_sample(sample_id, "streptococcus_pyogenes")])
    _patch_database(monkeypatch, fake)

    _rebuild(_make_options(
        tmp_path, backup_dir, profile="streptococcus_pyogenes",
    ))

    manifest = yaml.safe_load((tmp_path / "out" / f"{sample_id}_bonsai.yaml").read_text())
    entries = {(e["software"], e.get("subcommand")) for e in manifest["analysis_result"]}
    assert ("samtools", "coverage") in entries
    assert ("samtools", "stats") in entries
    assert ("samtools", "bedcov") in entries


def test_alignment_qc_not_resolved_for_generic_streptococcus(tmp_path, backup_dir, monkeypatch):
    """The generic streptococcus profile has no reference genome, so no alignment QC runs."""
    species = "streptococcus"
    sample_id = "sample1"
    _touch(backup_dir, species, "samtools_stats", f"{sample_id}.stats")
    _touch(backup_dir, species, "quast", f"{sample_id}_quast.tsv")

    fake = FakeMongo(samples=[_sample(sample_id, "streptococcus")])
    _patch_database(monkeypatch, fake)

    _rebuild(_make_options(tmp_path, backup_dir, profile="streptococcus"))

    manifest = yaml.safe_load((tmp_path / "out" / f"{sample_id}_bonsai.yaml").read_text())
    assert not any(e["uri"].endswith(".stats") for e in manifest["analysis_result"])


def test_legacy_postalignqc_used_when_samtools_absent(tmp_path, backup_dir, monkeypatch):
    """Older runs only wrote postalignqc/<sample_id>_qc.json."""
    species = "saureus"
    sample_id = "sample1"
    _touch(backup_dir, species, "postalignqc", f"{sample_id}_qc.json")
    _touch(backup_dir, species, "analysis_metadata", f"{sample_id}_analysis_meta.json", "{}")

    fake = FakeMongo(samples=[_sample(sample_id, "staphylococcus_aureus")])
    _patch_database(monkeypatch, fake)

    _rebuild(_make_options(tmp_path, backup_dir))

    manifest = yaml.safe_load((tmp_path / "out" / f"{sample_id}_bonsai.yaml").read_text())
    entries = {(e["software"], e.get("subcommand")) for e in manifest["analysis_result"]}
    assert ("postalignqc", None) in entries


@pytest.mark.parametrize("jasen_version, expected", [
    ("0.8.0", "0.9.3"),
    ("0.9.0", "0.10.0"),
    ("1.0.0", "0.11.4"),
    ("1.1.0", "1.3.1"),
    ("1.1.1", "1.3.1"),
    ("1.1.2", "1.3.3"),
    ("1.2.0", "1.5.0"),
    ("1.3.0", "1.0.0"),
])
def test_legacy_postalignqc_version_from_fallback(tmp_path, backup_dir, monkeypatch,
                                                  jasen_version, expected):
    """postalignqc has no key of its own in versions.yml; its version comes from the release."""
    species = "saureus"
    sample_id = "sample1"
    _touch(backup_dir, species, "postalignqc", f"{sample_id}_qc.json")
    fake = FakeMongo(samples=[_sample(sample_id, "staphylococcus_aureus")])
    _patch_database(monkeypatch, fake)

    _rebuild(_make_options(tmp_path, backup_dir, jasen_version=jasen_version))

    manifest = yaml.safe_load((tmp_path / "out" / f"{sample_id}_bonsai.yaml").read_text())
    entry = next(e for e in manifest["analysis_result"] if e["software"] == "postalignqc")
    assert entry["software_version"] == expected


def test_samtools_supersedes_legacy_postalignqc(tmp_path, backup_dir, monkeypatch):
    """When a sample has both, only the samtools outputs are kept."""
    species = "saureus"
    sample_id = "sample1"
    _touch(backup_dir, species, "postalignqc", f"{sample_id}_qc.json")
    _touch(backup_dir, species, "coverage", f"{sample_id}_bwa_mapcoverage.txt")
    _touch(backup_dir, species, "samtools_stats", f"{sample_id}.stats")
    _touch(backup_dir, species, "samtools_bedcov", f"{sample_id}.bedcov.tsv")
    _touch(backup_dir, species, "analysis_metadata", f"{sample_id}_analysis_meta.json", "{}")

    fake = FakeMongo(samples=[_sample(sample_id, "staphylococcus_aureus")])
    _patch_database(monkeypatch, fake)

    _rebuild(_make_options(tmp_path, backup_dir))

    manifest = yaml.safe_load((tmp_path / "out" / f"{sample_id}_bonsai.yaml").read_text())
    softwares = {e["software"] for e in manifest["analysis_result"]}
    assert "postalignqc" not in softwares
    assert "samtools" in softwares


def test_database_versions_read_from_meta_files(tmp_path, backup_dir, monkeypatch):
    """*_meta.json outputs become database_info entries tied to their tool."""
    species = "saureus"
    sample_id = "sample1"
    _touch(backup_dir, species, "resfinder", f"{sample_id}_resfinder.json")
    _touch(backup_dir, species, "virulencefinder", f"{sample_id}_virulencefinder.json")
    _touch(backup_dir, species, "resfinder", f"{sample_id}_resfinder_meta.json", json.dumps([
        {"name": "resfinder", "version": "2.6.0", "type": "database"},
        {"name": "pointfinder", "version": "4.1.1", "type": "database"},
    ]))
    _touch(backup_dir, species, "virulencefinder", f"{sample_id}_virulencefinder_meta.json",
           json.dumps({"name": "virulencefinder", "version": "2.0.1", "type": "database"}))

    fake = FakeMongo(samples=[_sample(sample_id, "staphylococcus_aureus")])
    _patch_database(monkeypatch, fake)

    _rebuild(_make_options(tmp_path, backup_dir))

    manifest = yaml.safe_load((tmp_path / "out" / f"{sample_id}_bonsai.yaml").read_text())
    assert "software_info" not in manifest
    assert manifest["database_info"] == [
        {"software": "resfinder", "name": "resfinder", "version": "2.6.0"},
        {"software": "pointfinder", "name": "pointfinder", "version": "4.1.1"},
        {"software": "virulencefinder", "name": "virulencefinder", "version": "2.0.1"},
    ]


def test_tbdb_version_from_jasen_release(tmp_path, backup_dir, monkeypatch):
    species = "mtuberculosis"
    sample_id = "sample1"
    _touch(backup_dir, species, "tbprofiler_mergedb", f"{sample_id}_tbprofiler.json")

    fake = FakeMongo(samples=[_sample(sample_id, "mycobacterium_tuberculosis")])
    _patch_database(monkeypatch, fake)

    _rebuild(_make_options(
        tmp_path, backup_dir, profile="mycobacterium_tuberculosis", jasen_version="1.3.0",
    ))

    manifest = yaml.safe_load((tmp_path / "out" / f"{sample_id}_bonsai.yaml").read_text())
    assert manifest["database_info"] == [
        {"software": "tbprofiler", "name": "tbdb",
         "version": "4907915526b52ac2f20f1324613f5d4dc951e0bd"},
    ]


@pytest.mark.parametrize("jasen_version, expected", [("0.8.0", "6.2.0"), ("0.9.0", "6.3.0")])
def test_tbprofiler_version_from_jasen_release(tmp_path, backup_dir, monkeypatch,
                                               jasen_version, expected):
    species = "mtuberculosis"
    sample_id = "sample1"
    _touch(backup_dir, species, "tbprofiler_mergedb", f"{sample_id}_tbprofiler.json")

    fake = FakeMongo(samples=[_sample(sample_id, "mycobacterium_tuberculosis")])
    _patch_database(monkeypatch, fake)

    _rebuild(_make_options(
        tmp_path, backup_dir, profile="mycobacterium_tuberculosis", jasen_version=jasen_version,
    ))

    versions = yaml.safe_load((tmp_path / "out" / f"{sample_id}_versions.yml").read_text())
    assert versions["jasentool_version_fallback"]["tb-profiler"] == {"version": expected}


# ── --sample-id filtering ──────────────────────────────────────────────────────

def test_symlinked_fields_taken_from_symlink_dir(tmp_path, backup_dir, monkeypatch):
    species = "saureus"
    sample_id = "sample1"
    symlink_dir = tmp_path / "access"
    for root in (backup_dir, symlink_dir):
        _touch(root, species, "sourmash", f"{sample_id}.sig")
        _touch(root, species, "ska", f"{sample_id}_ska_index.skf")
        _touch(root, species, "vcf", f"{sample_id}_freebayes.vcf")
    _touch(backup_dir, species, "quast", f"{sample_id}_quast.tsv")

    fake = FakeMongo(samples=[_sample(sample_id, "staphylococcus_aureus")])
    _patch_database(monkeypatch, fake)

    _rebuild(_make_options(tmp_path, backup_dir, symlink_dir=symlink_dir))

    manifest = yaml.safe_load((tmp_path / "out" / f"{sample_id}_bonsai.yaml").read_text())
    artifacts = manifest["index_artifacts"]
    assert artifacts["sourmash_signature"].startswith(str(symlink_dir))
    assert artifacts["ska_index"].startswith(str(symlink_dir))
    vcf_track = next(t for t in manifest["igv_annotations"] if t["type"] == "variant")
    assert vcf_track["uri"].startswith(str(symlink_dir))
    quast = next(e for e in manifest["analysis_result"] if e["software"] == "quast")
    assert quast["uri"].startswith(str(backup_dir))


def test_symlinked_bam_and_bai_taken_from_symlink_dir(tmp_path, backup_dir, monkeypatch):
    species = "mtuberculosis"
    sample_id = "sample1"
    symlink_dir = tmp_path / "access"
    for root in (backup_dir, symlink_dir):
        _touch(root, species, "bam", f"{sample_id}_tbprofiler.bam")
        _touch(root, species, "bam", f"{sample_id}_tbprofiler.bam.bai")

    fake = FakeMongo(samples=[_sample(sample_id, "mycobacterium_tuberculosis")])
    _patch_database(monkeypatch, fake)

    _rebuild(_make_options(
        tmp_path, backup_dir, profile="mycobacterium_tuberculosis", symlink_dir=symlink_dir,
    ))

    manifest = yaml.safe_load((tmp_path / "out" / f"{sample_id}_bonsai.yaml").read_text())
    bam_track = next(t for t in manifest["igv_annotations"] if t["type"] == "alignment")
    assert bam_track["uri"].startswith(str(symlink_dir))
    assert bam_track["index_uri"].startswith(str(symlink_dir))


def test_snippy_vcf_taken_from_vcf_dir_in_symlink_tree(tmp_path, backup_dir, monkeypatch):
    """The symlink tree groups by file type, so snippy's vcf is under vcf/, not snippy/."""
    species = "mtuberculosis"
    sample_id = "sample1"
    symlink_dir = tmp_path / "access"
    _touch(backup_dir, species, "snippy", f"{sample_id}_snippy.vcf")
    _touch(symlink_dir, species, "vcf", f"{sample_id}_snippy.vcf")

    fake = FakeMongo(samples=[_sample(sample_id, "mycobacterium_tuberculosis")])
    _patch_database(monkeypatch, fake)

    _rebuild(_make_options(
        tmp_path, backup_dir, profile="mycobacterium_tuberculosis", symlink_dir=symlink_dir,
    ))

    manifest = yaml.safe_load((tmp_path / "out" / f"{sample_id}_bonsai.yaml").read_text())
    vcf_track = next(t for t in manifest["igv_annotations"] if t["type"] == "variant")
    assert vcf_track["uri"] == str(symlink_dir / species / "vcf" / f"{sample_id}_snippy.vcf")


def test_symlinked_field_missing_from_symlink_dir_fails_sample(tmp_path, backup_dir,
                                                                monkeypatch, caplog):
    """Falling back to the backup path would give Bonsai a path it cannot read."""
    species = "saureus"
    sample_id = "sample1"
    symlink_dir = tmp_path / "access"
    _touch(backup_dir, species, "vcf", f"{sample_id}_freebayes.vcf")
    fake = FakeMongo(samples=[_sample(sample_id, "staphylococcus_aureus")])
    _patch_database(monkeypatch, fake)
    rebuild = RebuildManifests(_make_options(tmp_path, backup_dir, symlink_dir=symlink_dir))
    _add_missing_required_outputs(rebuild, [sample_id])
    (symlink_dir / species / "vcf" / f"{sample_id}_freebayes.vcf").unlink()

    with caplog.at_level(logging.WARNING):
        rebuild.run()

    assert not (tmp_path / "out" / f"{sample_id}_bonsai.yaml").exists()
    assert _failed_rows(tmp_path) == [{
        "sample_id": sample_id, "sample_name": "", "missing_output": "vcf (freebayes)",
        "expected_path": str(symlink_dir / species / "vcf" / f"{sample_id}_freebayes.vcf"),
    }]
    assert "not under" in caplog.text


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
    _rebuild(options)

    out_dir = tmp_path / "out"
    assert not (out_dir / "sample1_bonsai.yaml").exists()
    assert (out_dir / "sample2_bonsai.yaml").exists()


def test_unknown_sample_id_writes_nothing(tmp_path, backup_dir, monkeypatch, caplog):
    fake = FakeMongo(samples=[_sample("sample1", "staphylococcus_aureus")])
    _patch_database(monkeypatch, fake)

    options = _make_options(tmp_path, backup_dir, sample_id="does-not-exist")
    with caplog.at_level(logging.ERROR), pytest.raises(SystemExit):
        _rebuild(options)

    assert not (tmp_path / "out").exists()
    assert "does-not-exist" in caplog.text


# ── missing required outputs fail the sample ───────────────────────────────────

def _failed_rows(tmp_path):
    with open(tmp_path / "out" / FAILED_FILENAME, encoding="utf-8") as fin:
        return list(csv.DictReader(fin))


def test_sample_missing_required_outputs_is_failed(tmp_path, backup_dir, monkeypatch, caplog):
    sample_id = "sample1"
    _touch(backup_dir, "saureus", "quast", f"{sample_id}_quast.tsv")
    _touch(backup_dir, "saureus", "kraken", f"{sample_id}_bracken.out")
    fake = FakeMongo(samples=[_sample(sample_id, "staphylococcus_aureus", sample_name="Sample One")])
    _patch_database(monkeypatch, fake)

    with caplog.at_level(logging.WARNING):
        RebuildManifests(_make_options(tmp_path, backup_dir)).run()

    out_dir = tmp_path / "out"
    assert not (out_dir / f"{sample_id}_bonsai.yaml").exists()
    assert not (out_dir / f"{sample_id}_versions.yml").exists()
    rows = _failed_rows(tmp_path)
    assert {r["sample_name"] for r in rows} == {"Sample One"}
    assert [r["missing_output"] for r in rows] == [
        "sourmash", "save_analysis_metadata", "amrfinderplus", "resfinder_json",
        "resfinder_meta", "virulencefinder_json", "virulencefinder_meta", "chewbbaca",
        "mlst_json", "vcf (freebayes)",
    ]
    by_output = {r["missing_output"]: r["expected_path"] for r in rows}
    assert by_output["amrfinderplus"] == str(
        backup_dir / "saureus" / "amrfinderplus" / f"{sample_id}_amrfinder.tsv|"
        f"{sample_id}_amrfinder.out")
    assert "1 samples failed" in caplog.text


@pytest.mark.parametrize("release, required, not_required", [
    ("0.9.0", {"post_align_qc"},
     {"ska", "gambitcore", "samtools_coverage", "samtools_stats", "samtools_bedcov"}),
    ("1.3.0", {"ska", "gambitcore", "samtools_coverage", "post_align_qc"},
     {"samtools_stats", "samtools_bedcov"}),
    ("1.4.1", {"ska", "gambitcore", "samtools_coverage", "samtools_stats", "samtools_bedcov"},
     {"post_align_qc"}),
])
def test_required_outputs_follow_jasen_release(tmp_path, backup_dir, monkeypatch,
                                               release, required, not_required):
    _touch(backup_dir, "saureus", "analysis_metadata", "sample1_analysis_meta.json",
           json.dumps({"version": release}))
    fake = FakeMongo(samples=[_sample("sample1", "staphylococcus_aureus")])
    _patch_database(monkeypatch, fake)

    RebuildManifests(_make_options(tmp_path, backup_dir)).run()

    missing = {r["missing_output"] for r in _failed_rows(tmp_path)}
    assert required <= missing
    assert not missing & not_required


def test_species_typing_is_optional(tmp_path, backup_dir, monkeypatch):
    _touch(backup_dir, "ecoli", "analysis_metadata", "sample1_analysis_meta.json",
           json.dumps({"version": "1.4.1"}))
    fake = FakeMongo(samples=[_sample("sample1", "escherichia_coli")])
    _patch_database(monkeypatch, fake)

    _rebuild(_make_options(tmp_path, backup_dir, profile="escherichia_coli"))

    assert (tmp_path / "out" / "sample1_bonsai.yaml").exists()
    assert not (backup_dir / "ecoli" / "shigatyper" / "sample1.tsv").exists()
    assert not (backup_dir / "ecoli" / "serotypefinder").exists()


def test_tb_tools_are_required(tmp_path, backup_dir, monkeypatch):
    fake = FakeMongo(samples=[_sample("sample1", "mycobacterium_tuberculosis")])
    _patch_database(monkeypatch, fake)

    RebuildManifests(_make_options(tmp_path, backup_dir,
                                   profile="mycobacterium_tuberculosis")).run()

    missing = {r["missing_output"] for r in _failed_rows(tmp_path)}
    assert {"tbprofiler_json", "tbprofiler_bam", "tbprofiler_bai", "mykrobe"} <= missing
    assert any(m.startswith("vcf (") for m in missing)


def test_no_bonsai_ignores_old_manifests(tmp_path, backup_dir, monkeypatch):
    _forbid_database(monkeypatch)
    _touch(backup_dir, "saureus", "quast", "sample1_quast.tsv")
    _touch(backup_dir, "saureus", "analysis_yaml", "sample1_bonsai.yaml")
    _touch(backup_dir, "saureus", "analysis_yaml", "sample2.yaml")

    _rebuild(_make_options(tmp_path, backup_dir, no_bonsai=True))

    assert sorted(p.name for p in (tmp_path / "out").glob("*_bonsai.yaml")) == [
        "sample1_bonsai.yaml"]


def test_only_incomplete_samples_fail(tmp_path, backup_dir, monkeypatch):
    fake = FakeMongo(samples=[_sample("complete", "staphylococcus_aureus"),
                              _sample("incomplete", "staphylococcus_aureus")])
    _patch_database(monkeypatch, fake)
    rebuild = RebuildManifests(_make_options(tmp_path, backup_dir))
    _add_missing_required_outputs(rebuild, ["complete", "incomplete"])
    (backup_dir / "saureus" / "chewbbaca" / "incomplete_chewbbaca.tsv").unlink()

    rebuild.run()

    assert (tmp_path / "out" / "complete_bonsai.yaml").exists()
    assert not (tmp_path / "out" / "incomplete_bonsai.yaml").exists()
    assert [(r["sample_id"], r["missing_output"]) for r in _failed_rows(tmp_path)] == [
        ("incomplete", "chewbbaca")]


def test_unreadable_run_metadata_fails_sample(tmp_path, backup_dir, monkeypatch):
    fake = FakeMongo(samples=[_sample("sample1", "staphylococcus_aureus")])
    _patch_database(monkeypatch, fake)
    _touch(backup_dir, "saureus", "analysis_metadata", "sample1_analysis_meta.json", "not json")

    _rebuild(_make_options(tmp_path, backup_dir))

    assert [r["missing_output"] for r in _failed_rows(tmp_path)] == ["save_analysis_metadata"]


def test_failed_summary_written_when_nothing_fails(tmp_path, backup_dir, monkeypatch):
    fake = FakeMongo(samples=[_sample("sample1", "staphylococcus_aureus")])
    _patch_database(monkeypatch, fake)

    _rebuild(_make_options(tmp_path, backup_dir))

    assert (tmp_path / "out" / "sample1_bonsai.yaml").exists()
    assert (tmp_path / "out" / FAILED_FILENAME).read_text().splitlines() == [
        "sample_id,sample_name,missing_output,expected_path"]


# ── TB vcf priority (tbprofiler_vcf > snippy_vcf) ──────────────────────────────

def test_tb_prefers_tbprofiler_vcf_over_snippy(tmp_path, backup_dir, monkeypatch):
    species = "mtuberculosis"
    sample_id = "sample1"
    tbprofiler_vcf = _touch(backup_dir, species, "vcf", f"{sample_id}_tbprofiler.vcf.gz")
    _touch(backup_dir, species, "snippy", f"{sample_id}_snippy.vcf")

    fake = FakeMongo(samples=[_sample(sample_id, "mycobacterium_tuberculosis")])
    _patch_database(monkeypatch, fake)

    options = _make_options(tmp_path, backup_dir, profile="mycobacterium_tuberculosis")
    _rebuild(options)

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
    _rebuild(options)

    manifest = yaml.safe_load((tmp_path / "out" / f"{sample_id}_bonsai.yaml").read_text())
    variants = next(e for e in manifest["igv_annotations"] if e["name"] == "Predicted variants")
    assert variants["uri"] == str(snippy_vcf)


def test_bwa_bam_and_bai_resolved(tmp_path, backup_dir, monkeypatch):
    species = "saureus"
    sample_id = "sample1"
    bam = _touch(backup_dir, species, "bam", f"{sample_id}_bwa.bam")
    bai = _touch(backup_dir, species, "bam", f"{sample_id}_bwa.bam.bai")

    fake = FakeMongo(samples=[_sample(sample_id, "staphylococcus_aureus")])
    _patch_database(monkeypatch, fake)

    _rebuild(_make_options(tmp_path, backup_dir))

    manifest = yaml.safe_load((tmp_path / "out" / f"{sample_id}_bonsai.yaml").read_text())
    track = next(t for t in manifest["igv_annotations"] if t["type"] == "alignment")
    assert track["uri"] == str(bam)
    assert track["index_uri"] == str(bai)


def test_bwa_bam_and_bai_taken_from_symlink_dir(tmp_path, backup_dir, monkeypatch):
    species = "saureus"
    sample_id = "sample1"
    symlink_dir = tmp_path / "access"
    for root in (backup_dir, symlink_dir):
        _touch(root, species, "bam", f"{sample_id}_bwa.bam")
        _touch(root, species, "bam", f"{sample_id}_bwa.bam.bai")

    fake = FakeMongo(samples=[_sample(sample_id, "staphylococcus_aureus")])
    _patch_database(monkeypatch, fake)

    _rebuild(_make_options(tmp_path, backup_dir, symlink_dir=symlink_dir))

    manifest = yaml.safe_load((tmp_path / "out" / f"{sample_id}_bonsai.yaml").read_text())
    track = next(t for t in manifest["igv_annotations"] if t["type"] == "alignment")
    assert track["uri"] == str(symlink_dir / species / "bam" / f"{sample_id}_bwa.bam")
    assert track["index_uri"] == str(symlink_dir / species / "bam" / f"{sample_id}_bwa.bam.bai")


def test_tb_bam_and_bai_resolved(tmp_path, backup_dir, monkeypatch):
    species = "mtuberculosis"
    sample_id = "sample1"
    bam_path = _touch(backup_dir, species, "bam", f"{sample_id}_tbprofiler.bam")
    bai_path = _touch(backup_dir, species, "bam", f"{sample_id}_tbprofiler.bam.bai")

    fake = FakeMongo(samples=[_sample(sample_id, "mycobacterium_tuberculosis")])
    _patch_database(monkeypatch, fake)

    options = _make_options(tmp_path, backup_dir, profile="mycobacterium_tuberculosis")
    _rebuild(options)

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

    _rebuild(_make_options(tmp_path, backup_dir))

    manifest = yaml.safe_load((tmp_path / "out" / f"{sample_id}_bonsai.yaml").read_text())
    assert manifest["groups"] == ["saureus", "wgs", "outbreak_2026"]


def test_sample_in_no_groups_gets_profile_group(tmp_path, backup_dir, monkeypatch):
    sample_id = "sample1"
    fake = FakeMongo(samples=[_sample(sample_id, "staphylococcus_aureus")], groups=[])
    _patch_database(monkeypatch, fake)

    _rebuild(_make_options(tmp_path, backup_dir))

    manifest = yaml.safe_load((tmp_path / "out" / f"{sample_id}_bonsai.yaml").read_text())
    assert manifest["groups"] == ["saureus"]


@pytest.mark.parametrize("profile, species, group", [
    ("staphylococcus_aureus", "saureus", "saureus"),
    ("escherichia_coli", "ecoli", "ecoli"),
    ("mycobacterium_tuberculosis", "mtuberculosis", "mtuberculosis"),
    ("streptococcus_pyogenes", "spyogenes", "spyogenes"),
    ("streptococcus", "streptococcus", "streptococcus"),
])
def test_profile_converted_to_group_without_bonsai(tmp_path, backup_dir, monkeypatch,
                                                   profile, species, group):
    sample_id = "sample1"
    _touch(backup_dir, species, "quast", f"{sample_id}_quast.tsv")
    _forbid_database(monkeypatch)

    _rebuild(_make_options(tmp_path, backup_dir, profile=profile, no_bonsai=True))

    manifest = yaml.safe_load((tmp_path / "out" / f"{sample_id}_bonsai.yaml").read_text())
    assert manifest["groups"] == [group]


def test_duplicate_profile_group_from_bonsai_not_repeated(tmp_path, backup_dir, monkeypatch):
    sample_id = "sample1"
    fake = FakeMongo(
        samples=[_sample(sample_id, "staphylococcus_aureus")],
        groups=[{"name": "saureus", "included_samples": [sample_id]}],
    )
    _patch_database(monkeypatch, fake)

    _rebuild(_make_options(tmp_path, backup_dir))

    manifest = yaml.safe_load((tmp_path / "out" / f"{sample_id}_bonsai.yaml").read_text())
    assert manifest["groups"] == ["saureus"]


def test_bracken_output_resolved_from_kraken_dir(tmp_path, backup_dir, monkeypatch):
    """Backed-up runs published bracken into kraken/, before kraken had its own output."""
    species = "saureus"
    sample_id = "sample1"
    _touch(backup_dir, species, "kraken", f"{sample_id}_bracken.out")
    _touch(backup_dir, species, "kraken", f"{sample_id}_bracken.report")
    _touch(backup_dir, species, "kraken", f"{sample_id}_kraken.report")
    _touch(backup_dir, species, "analysis_metadata", f"{sample_id}_analysis_meta.json", "{}")

    fake = FakeMongo(samples=[_sample(sample_id, "staphylococcus_aureus")])
    _patch_database(monkeypatch, fake)

    _rebuild(_make_options(tmp_path, backup_dir))

    manifest = yaml.safe_load((tmp_path / "out" / f"{sample_id}_bonsai.yaml").read_text())
    entries = {e["software"]: e["uri"] for e in manifest["analysis_result"]}
    assert entries["bracken"].endswith(f"{sample_id}_bracken.out")
    assert not any(uri.endswith("_kraken.report") for uri in entries.values())


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

    _rebuild(_make_options(tmp_path, backup_dir, no_bonsai=True))

    out_dir = tmp_path / "out"
    for sid in ("sampleA", "sample_with_underscores"):
        manifest = yaml.safe_load((out_dir / f"{sid}_bonsai.yaml").read_text())
        assert manifest["sample_id"] == sid
        assert manifest["sample_name"] == sid       # falls back to sample_id
        assert "lims_id" not in manifest            # unset -> omitted
        assert manifest["groups"] == ["saureus"]    # from the profile, no Bonsai lookup
        results = {e["software"]: e for e in manifest["analysis_result"]}
        assert results["quast"]["software_version"] == "5.2.0"
        assert (out_dir / f"{sid}_versions.yml").exists()


def test_no_bonsai_sample_id_filters(tmp_path, backup_dir, monkeypatch):
    species = "saureus"
    for sid in ("sample1", "sample2"):
        _touch(backup_dir, species, "quast", f"{sid}_quast.tsv")
    _forbid_database(monkeypatch)

    options = _make_options(tmp_path, backup_dir, no_bonsai=True, sample_id="sample2")
    _rebuild(options)

    out_dir = tmp_path / "out"
    assert not (out_dir / "sample1_bonsai.yaml").exists()
    assert (out_dir / "sample2_bonsai.yaml").exists()


def test_no_bonsai_unknown_sample_id_writes_nothing(tmp_path, backup_dir, monkeypatch, caplog):
    _touch(backup_dir, "saureus", "quast", "sample1_quast.tsv")
    _forbid_database(monkeypatch)

    options = _make_options(tmp_path, backup_dir, no_bonsai=True, sample_id="nope")
    with caplog.at_level(logging.ERROR):
        _rebuild(options)

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

    _rebuild(_make_options(tmp_path, backup_dir, no_bonsai=True))

    out_dir = tmp_path / "out"
    assert (out_dir / "realSample_bonsai.yaml").exists()
    assert not (out_dir / "ghost_bonsai.yaml").exists()


def _stale_manifest_setup(tmp_path, backup_dir):
    for sample_id in ("S1", "S2"):
        _touch(backup_dir, "saureus", "quast", f"{sample_id}_quast.tsv")
    out = tmp_path / "out"
    out.mkdir()
    (out / "S1_bonsai.yaml").write_text("stale\n")
    return out


def test_existing_manifest_skipped_without_force(tmp_path, backup_dir):
    out = _stale_manifest_setup(tmp_path, backup_dir)

    _rebuild(_make_options(tmp_path, backup_dir, no_bonsai=True))

    assert (out / "S1_bonsai.yaml").read_text() == "stale\n"
    assert yaml.safe_load((out / "S2_bonsai.yaml").read_text())["sample_id"] == "S2"


def test_force_overwrites_existing_manifest(tmp_path, backup_dir):
    out = _stale_manifest_setup(tmp_path, backup_dir)

    _rebuild(_make_options(tmp_path, backup_dir, no_bonsai=True, force=True))

    assert yaml.safe_load((out / "S1_bonsai.yaml").read_text())["sample_id"] == "S1"
    assert yaml.safe_load((out / "S2_bonsai.yaml").read_text())["sample_id"] == "S2"


def _tb_variant_track(tmp_path, backup_dir, monkeypatch, symlink_dir=None):
    fake = FakeMongo(samples=[_sample("sample1", "mycobacterium_tuberculosis")])
    _patch_database(monkeypatch, fake)
    options = _make_options(tmp_path, backup_dir, profile="mycobacterium_tuberculosis",
                            symlink_dir=symlink_dir)
    _rebuild(options)
    manifest = yaml.safe_load((tmp_path / "out" / "sample1_bonsai.yaml").read_text())
    return next(e for e in manifest["igv_annotations"] if e["name"] == "Predicted variants")


def test_tb_prefers_annotated_delly_vcf(tmp_path, backup_dir, monkeypatch):
    _touch(backup_dir, "mtuberculosis", "vcf", "sample1_tbprofiler.vcf.gz")
    annotated = _touch(backup_dir, "mtuberculosis", "vcf", "sample1_annotated_delly.vcf")

    assert _tb_variant_track(tmp_path, backup_dir, monkeypatch)["uri"] == str(annotated)


def test_tb_annotated_delly_vcf_taken_from_symlink_dir(tmp_path, backup_dir, monkeypatch):
    symlink_dir = tmp_path / "access"
    _touch(backup_dir, "mtuberculosis", "vcf", "sample1_tbprofiler.vcf.gz")
    _touch(backup_dir, "mtuberculosis", "vcf", "sample1_annotated_delly.vcf")
    linked = _touch(symlink_dir, "mtuberculosis", "vcf", "sample1_annotated_delly.vcf")

    track = _tb_variant_track(tmp_path, backup_dir, monkeypatch, symlink_dir=symlink_dir)
    assert track["uri"] == str(linked)


def _igv_tracks(tmp_path, backup_dir, monkeypatch, profile, **kwargs):
    species = {"mycobacterium_tuberculosis": "mtuberculosis",
               "staphylococcus_aureus": "saureus"}[profile]
    fake = FakeMongo(samples=[_sample("sample1", profile)])
    _patch_database(monkeypatch, fake)
    _touch(backup_dir, species, "vcf", "sample1_annotated_delly.vcf")
    _rebuild(_make_options(tmp_path, backup_dir, profile=profile, **kwargs))
    manifest = yaml.safe_load((tmp_path / "out" / "sample1_bonsai.yaml").read_text())
    return manifest["igv_annotations"]


def test_tb_bed_tracks_taken_from_assets_dir(tmp_path, backup_dir, monkeypatch):
    assets_dir = tmp_path / "jasen" / "assets"
    symlink_dir = tmp_path / "access"
    linked_vcf = _touch(symlink_dir, "mtuberculosis", "vcf", "sample1_annotated_delly.vcf")

    tracks = _igv_tracks(tmp_path, backup_dir, monkeypatch, "mycobacterium_tuberculosis",
                         assets_dir=assets_dir, symlink_dir=symlink_dir)

    assert [t for t in tracks if t["type"] != "alignment"] == [
        {"name": "tbdb grading rules bed", "type": "bed",
         "uri": str(assets_dir / "tb_info" / "bed" / "tb_grading_rules.bed")},
        {"name": "tbdb bed", "type": "bed",
         "uri": str(assets_dir / "tbdb" / "converged_who_fohm_tbdb.bed.gz")},
        {"name": "Predicted variants", "type": "variant", "uri": str(linked_vcf)},
    ]


def test_tb_bed_tracks_left_out_without_assets_dir(tmp_path, backup_dir, monkeypatch):
    tracks = _igv_tracks(tmp_path, backup_dir, monkeypatch, "mycobacterium_tuberculosis")

    assert "bed" not in [t["type"] for t in tracks]


def test_assets_dir_adds_nothing_for_non_tb_profile(tmp_path, backup_dir, monkeypatch):
    tracks = _igv_tracks(tmp_path, backup_dir, monkeypatch, "staphylococcus_aureus",
                         assets_dir=tmp_path / "assets")

    assert not any(t["type"] == "bed" for t in tracks)


def _release_fallback_run(tmp_path, backup_dir, monkeypatch, meta_version, jasen_version=None):
    _touch(backup_dir, "saureus", "chewbbaca", "sample1_chewbbaca.tsv")
    _touch(backup_dir, "saureus", "analysis_metadata", "sample1_analysis_meta.json",
           json.dumps({"version": meta_version, "lims_id": "L1"}))
    monkeypatch.setattr(
        "jasentool.rebuild_manifests.VERSIONS_FALLBACK",
        {"1.1.0": {"chewbbaca": "3.3.2"}, "1.3.0": {"chewbbaca": "3.5.3"}},
    )
    _patch_database(monkeypatch, FakeMongo(samples=[_sample("sample1", "staphylococcus_aureus")]))
    _rebuild(_make_options(tmp_path, backup_dir, jasen_version=jasen_version))
    manifest = yaml.safe_load((tmp_path / "out" / "sample1_bonsai.yaml").read_text())
    return {e["software"]: e for e in manifest["analysis_result"]}["chewbbaca"]


def test_versions_fallback_uses_release_from_run_metadata(tmp_path, backup_dir, monkeypatch):
    chewbbaca = _release_fallback_run(tmp_path, backup_dir, monkeypatch, "1.3.0")

    assert chewbbaca["software_version"] == "3.5.3"
    versions = yaml.safe_load((tmp_path / "out" / "sample1_versions.yml").read_text())
    assert versions["jasentool_version_fallback"]["chewbbaca"]["version"] == "3.5.3"


def test_jasen_version_overrides_run_metadata_release(tmp_path, backup_dir, monkeypatch):
    chewbbaca = _release_fallback_run(tmp_path, backup_dir, monkeypatch, "1.3.0",
                                      jasen_version="1.1.0")

    assert chewbbaca["software_version"] == "3.3.2"


def test_unknown_release_leaves_version_missing(tmp_path, backup_dir, monkeypatch, caplog):
    chewbbaca = _release_fallback_run(tmp_path, backup_dir, monkeypatch, "9.9.9")

    assert "software_version" not in chewbbaca
    assert "release 9.9.9 has no versions fallback" in caplog.text
