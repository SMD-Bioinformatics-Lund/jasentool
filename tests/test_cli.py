"""Tests for the jasentool CLI."""
import json

import pytest
from click.testing import CliRunner

from jasentool.cli import cli

runner = CliRunner()


# ── count-reads ────────────────────────────────────────────────────────────────

def test_count_reads_plain_fastq(fastq_file, tmp_path):
    out = tmp_path / "out.json"
    result = runner.invoke(cli, ["count-reads", "-i", str(fastq_file), "-o", str(out)])
    assert result.exit_code == 0, result.output
    data = json.loads(out.read_text())
    assert data["n_reads"] == 10
    assert data["n_read_pairs"] == 5


def test_count_reads_gzipped(fastq_gz_file, tmp_path):
    out = tmp_path / "out.json"
    result = runner.invoke(cli, ["count-reads", "-i", str(fastq_gz_file), "-o", str(out)])
    assert result.exit_code == 0, result.output


def test_count_reads_two_files(fastq_file, tmp_path):
    out = tmp_path / "out.json"
    result = runner.invoke(cli, [
        "count-reads", "-i", str(fastq_file), "-i", str(fastq_file), "-o", str(out)
    ])
    assert result.exit_code == 0, result.output
    data = json.loads(out.read_text())
    assert data["n_read_pairs"] == 10  # R1 + R2 both 10 reads, pairs = R1 count


def test_count_reads_with_sample_id(fastq_file, tmp_path):
    out = tmp_path / "out.json"
    result = runner.invoke(cli, [
        "count-reads", "-i", str(fastq_file), "-o", str(out), "--sample-id", "SAMP1"
    ])
    assert result.exit_code == 0, result.output
    assert json.loads(out.read_text())["sample_id"] == "SAMP1"


def test_count_reads_missing_input():
    result = runner.invoke(cli, ["count-reads", "-o", "/tmp/out.json"])
    assert result.exit_code != 0


# ── transform-file-format ──────────────────────────────────────────────────────

def test_transform_file_format_help():
    result = runner.invoke(cli, ["transform-file-format", "--help"])
    assert result.exit_code == 0


def test_transform_missing_args():
    result = runner.invoke(cli, ["transform-file-format"])
    assert result.exit_code != 0


# ── --help for all remaining subcommands ──────────────────────────────────────

@pytest.mark.parametrize("subcommand", [
    "find", "validate-pipelines", "identify-missing",
    "reformat-csv", "converge-catalogues", "post-align-qc",
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
])
def test_missing_required_args(subcommand, args):
    result = runner.invoke(cli, [subcommand] + args)
    assert result.exit_code != 0
