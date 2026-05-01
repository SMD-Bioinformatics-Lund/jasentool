"""Tests for the jasentool CLI."""
import json

import yaml

import pytest
from click.testing import CliRunner

from jasentool.cli import cli

runner = CliRunner()


# ── count-reads ────────────────────────────────────────────────────────────────

def test_count_reads_plain_fastq(fastq_file, tmp_path):
    out = tmp_path / "out.json"
    result = runner.invoke(cli, ["count-reads", "--fastq1", str(fastq_file), "-o", str(out)])
    assert result.exit_code == 0, result.output
    data = json.loads(out.read_text())
    assert data["n_reads"] == 10
    assert data["n_read_pairs"] == 5


def test_count_reads_gzipped(fastq_gz_file, tmp_path):
    out = tmp_path / "out.json"
    result = runner.invoke(cli, ["count-reads", "--fastq1", str(fastq_gz_file), "-o", str(out)])
    assert result.exit_code == 0, result.output


def test_count_reads_two_files(fastq_file, tmp_path):
    out = tmp_path / "out.json"
    result = runner.invoke(cli, [
        "count-reads", "--fastq1", str(fastq_file), "--fastq2", str(fastq_file), "-o", str(out)
    ])
    assert result.exit_code == 0, result.output
    data = json.loads(out.read_text())
    assert data["n_read_pairs"] == 10  # R1 + R2 both 10 reads, pairs = R1 count


def test_count_reads_with_sample_id(fastq_file, tmp_path):
    out = tmp_path / "out.json"
    result = runner.invoke(cli, [
        "count-reads", "--fastq1", str(fastq_file), "-o", str(out), "--sample-id", "SAMP1"
    ])
    assert result.exit_code == 0, result.output
    assert json.loads(out.read_text())["sample_id"] == "SAMP1"


def test_count_reads_missing_input():
    result = runner.invoke(cli, ["count-reads", "-o", "/tmp/out.json"])
    assert result.exit_code != 0


def test_count_reads_saureus_paired(saureus_fastq_r1, saureus_fastq_r2, tmp_path):
    out = tmp_path / "counts.json"
    result = runner.invoke(cli, [
        "count-reads",
        "--fastq1", str(saureus_fastq_r1),
        "--fastq2", str(saureus_fastq_r2),
        "-o", str(out),
    ])
    assert result.exit_code == 0, result.output
    data = json.loads(out.read_text())
    assert data["n_reads"] == 38702
    assert data["n_read_pairs"] == 19351


# ── transform-file-format ──────────────────────────────────────────────────────

def test_transform_file_format_help():
    result = runner.invoke(cli, ["transform-file-format", "--help"])
    assert result.exit_code == 0


def test_transform_missing_args():
    result = runner.invoke(cli, ["transform-file-format"])
    assert result.exit_code != 0


def test_transform_cgmlst_csv_to_bed(cgmlst_csv, tmp_path):
    """Convert the S. aureus cgMLST targets CSV (tab-separated) to BED format."""
    out = tmp_path / "targets.bed"
    accession = "NC_002951.2"
    result = runner.invoke(cli, [
        "transform-file-format",
        "-i", str(cgmlst_csv),
        "-o", str(out),
        "-a", accession,
    ])
    assert result.exit_code == 0, result.output
    lines = out.read_text().splitlines()
    assert len(lines) == 10
    # Verify first and last entries match expected 0-based BED coordinates
    # SACOL0001: start=544 → 543 (0-based), length=1362 → end=1905
    assert lines[0] == f"{accession}\t543\t1905"
    # SACOL0011: start=15441 → 15440 (0-based), length=330 → end=15770
    assert lines[-1] == f"{accession}\t15440\t15770"


def test_transform_cgmlst_csv_bed_columns(cgmlst_csv, tmp_path):
    """Each BED line must have exactly three tab-separated columns."""
    out = tmp_path / "targets.bed"
    result = runner.invoke(cli, [
        "transform-file-format",
        "-i", str(cgmlst_csv),
        "-o", str(out),
        "-a", "NC_002951.2",
    ])
    assert result.exit_code == 0, result.output
    for line in out.read_text().splitlines():
        cols = line.split("\t")
        assert len(cols) == 3
        assert int(cols[1]) >= 0
        assert int(cols[2]) > int(cols[1])


# ── --help for all remaining subcommands ──────────────────────────────────────

@pytest.mark.parametrize("subcommand", [
    "find", "validate-pipelines", "identify-missing",
    "reformat-csv", "converge-catalogues", "post-align-qc",
    "concatenate-files", "create-yaml",
])
def test_help_exits_zero(subcommand):
    result = runner.invoke(cli, [subcommand, "--help"])
    assert result.exit_code == 0
    assert subcommand in result.output or "Usage" in result.output


# ── missing required args exits non-zero ──────────────────────────────────────

@pytest.mark.parametrize("subcommand,args", [
    ("find", []),
    ("validate-pipelines", []),
    ("identify-missing", []),
    ("post-align-qc", []),
    ("reformat-csv", []),
    ("concatenate-files", []),
    ("create-yaml", []),
])
def test_missing_required_args(subcommand, args):
    result = runner.invoke(cli, [subcommand] + args)
    assert result.exit_code != 0


# ── concatenate-files ──────────────────────────────────────────────────────────

def test_concatenate_files(versions_yaml_a, versions_yaml_b, tmp_path):
    out = tmp_path / "merged.yml"
    result = runner.invoke(cli, [
        "concatenate-files",
        "-i", str(versions_yaml_a),
        "-i", str(versions_yaml_b),
        "-o", str(out),
    ])
    assert result.exit_code == 0, result.output
    data = yaml.safe_load(out.read_text())
    assert "tool_a" in data
    assert "tool_b" in data


def test_concatenate_files_missing_args():
    result = runner.invoke(cli, ["concatenate-files"])
    assert result.exit_code != 0


# ── create-yaml ────────────────────────────────────────────────────────────────

def test_create_yaml_minimal(tmp_path):
    out = tmp_path / "input.yml"
    result = runner.invoke(cli, [
        "create-yaml",
        "--sample-id", "SAMP001",
        "--sample-name", "Sample 001",
        "--groups", "group1",
        "--plasmidfinder", "plasmidfinder.json",
        "-o", str(out),
    ])
    assert result.exit_code == 0, result.output
    data = yaml.safe_load(out.read_text())
    assert data["sample_id"] == "SAMP001"
    assert data["sample_name"] == "Sample 001"
    assert data["groups"] == ["group1"]
    assert data["igv_annotations"] == []
    assert data["plasmidfinder"] == "plasmidfinder.json"


def test_create_yaml_with_bam_and_bai(tmp_path):
    out = tmp_path / "input.yml"
    result = runner.invoke(cli, [
        "create-yaml",
        "--sample-id", "SAMP002",
        "--sample-name", "Sample 002",
        "--groups", "group1",
        "--bam", "sample.bam",
        "--bai", "sample.bam.bai",
        "-o", str(out),
    ])
    assert result.exit_code == 0, result.output
    data = yaml.safe_load(out.read_text())
    igv = data["igv_annotations"]
    assert len(igv) == 1
    assert igv[0]["type"] == "alignment"
    assert igv[0]["index_uri"] == "sample.bam.bai"


def test_create_yaml_missing_required_args():
    result = runner.invoke(cli, ["create-yaml"])
    assert result.exit_code != 0


# ── annotate-delly ─────────────────────────────────────────────────────────────

def test_annotate_delly(delly_bcf_path, delly_bed_path, tmp_path):
    out = tmp_path / "annotated.vcf"
    result = runner.invoke(cli, [
        "annotate-delly",
        "-v", str(delly_bcf_path),
        "-b", str(delly_bed_path),
        "-o", str(out),
    ])
    assert result.exit_code == 0, result.output
    assert out.exists()


# ── post-align-qc ─────────────────────────────────────────────────────────────

def test_post_align_qc(saureus_bam_path, tmp_path):
    out = tmp_path / "qc.json"
    result = runner.invoke(cli, [
        "post-align-qc",
        "--sample-id", "saureus_test_1",
        "--bam-file", str(saureus_bam_path),
        "-o", str(out),
    ])
    assert result.exit_code == 0, result.output
    assert out.exists()
    data = json.loads(out.read_text())
    assert data["sample_id"] == "saureus_test_1"
    assert data["n_reads"] > 0
    assert data["n_mapped_reads"] > 0
    assert data["mean_cov"] is not None
    assert "pct_above_x" in data


# ── download-ncbi ──────────────────────────────────────────────────────────────

def test_download_ncbi_help():
    result = runner.invoke(cli, ["download-ncbi", "--help"])
    assert result.exit_code == 0


def test_download_ncbi_missing_args():
    result = runner.invoke(cli, ["download-ncbi"])
    assert result.exit_code != 0


def test_download_ncbi(tmp_path):
    result = runner.invoke(cli, [
        "download-ncbi", "-i", "GCF_000012045.1", "-o", str(tmp_path),
    ])
    assert result.exit_code == 0, result.output
    fasta = tmp_path / "GCF_000012045.1.fasta"
    gff   = tmp_path / "GCF_000012045.1.gff"
    assert fasta.exists() and fasta.stat().st_size > 0
    assert gff.exists()   and gff.stat().st_size > 0
