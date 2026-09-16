"""Tests for database_info in create-yaml manifests."""
import json

import yaml
from click.testing import CliRunner

from jasentool.cli import cli

runner = CliRunner()


def _write_json(path, content):
    path.write_text(json.dumps(content))
    return str(path)


def _create_yaml(tmp_path, *args):
    out = tmp_path / "manifest.yml"
    result = runner.invoke(cli, [
        "create-yaml", "--sample-id", "S1", "--sample-name", "S1", "--groups", "saureus",
        *args, "-o", str(out),
    ])
    assert result.exit_code == 0, result.output
    return yaml.safe_load(out.read_text())


def test_versions_read_from_meta_files(tmp_path):
    resfinder_meta = _write_json(tmp_path / "S1_resfinder_meta.json", [
        {"name": "resfinder", "version": "2.6.0", "type": "database"},
        {"name": "pointfinder", "version": "4.1.1", "type": "database"},
    ])
    virulencefinder_meta = _write_json(
        tmp_path / "S1_virulencefinder_meta.json",
        {"name": "virulencefinder", "version": "2.0.1", "type": "database"},
    )
    data = _create_yaml(
        tmp_path,
        "--resfinder", "resfinder.json", "--virulencefinder", "virulencefinder.json",
        "--database-info", resfinder_meta, "--database-info", virulencefinder_meta,
    )
    assert data["database_info"] == [
        {"software": "resfinder", "name": "resfinder", "version": "2.6.0"},
        {"software": "pointfinder", "name": "pointfinder", "version": "4.1.1"},
        {"software": "virulencefinder", "name": "virulencefinder", "version": "2.0.1"},
    ]


def test_release_fallback_fills_missing_meta_and_tbdb(tmp_path):
    data = _create_yaml(
        tmp_path,
        "--resfinder", "resfinder.json", "--tbprofiler", "tbprofiler.json",
        "--jasen-version", "1.3.0",
    )
    assert data["database_info"] == [
        {"software": "resfinder", "name": "resfinder", "version": "2.6.0"},
        {"software": "pointfinder", "name": "pointfinder", "version": "4.1.1"},
        {"software": "tbprofiler", "name": "tbdb",
         "version": "4907915526b52ac2f20f1324613f5d4dc951e0bd"},
    ]


def test_release_taken_from_run_info(tmp_path):
    run_info = _write_json(tmp_path / "analysis_meta.json", {"version": "1.2.0"})
    data = _create_yaml(
        tmp_path, "--tbprofiler", "tbprofiler.json", "--nextflow-run-info", run_info,
    )
    assert data["database_info"] == [
        {"software": "tbprofiler", "name": "tbdb",
         "version": "4907915526b52ac2f20f1324613f5d4dc951e0bd"},
    ]


def test_jasen_version_wins_over_run_info(tmp_path):
    run_info = _write_json(tmp_path / "analysis_meta.json", {"version": "1.1.0"})
    data = _create_yaml(
        tmp_path, "--resfinder", "resfinder.json", "--nextflow-run-info", run_info,
        "--jasen-version", "1.2.0",
    )
    assert data["database_info"][0]["version"] == "2.6.0"


def test_submodule_era_release_uses_commit_ids(tmp_path):
    data = _create_yaml(
        tmp_path, "--virulencefinder", "virulencefinder.json", "--jasen-version", "1.1.2",
    )
    assert data["database_info"] == [
        {"software": "virulencefinder", "name": "virulencefinder",
         "version": "9638945ea72ec748beded45bb9fe48351eee346f"},
    ]


def test_unknown_meta_version_uses_fallback(tmp_path):
    meta = _write_json(
        tmp_path / "S1_virulencefinder_meta.json",
        {"name": "virulencefinder", "version": "unknown", "type": "database"},
    )
    data = _create_yaml(
        tmp_path, "--virulencefinder", "virulencefinder.json",
        "--database-info", meta, "--jasen-version", "1.2.0",
    )
    assert data["database_info"] == [
        {"software": "virulencefinder", "name": "virulencefinder", "version": "2.0.1"},
    ]


def test_database_without_its_tool_is_left_out(tmp_path):
    meta = _write_json(
        tmp_path / "S1_virulencefinder_meta.json",
        {"name": "virulencefinder", "version": "2.0.1", "type": "database"},
    )
    data = _create_yaml(tmp_path, "--quast", "quast.tsv", "--database-info", meta)
    assert "database_info" not in data


def test_no_version_anywhere_is_left_out(tmp_path):
    data = _create_yaml(tmp_path, "--tbprofiler", "tbprofiler.json")
    assert "database_info" not in data
