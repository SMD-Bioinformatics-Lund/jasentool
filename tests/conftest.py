"""Shared pytest fixtures."""
import gzip
from pathlib import Path
import pytest

TESTS_DIR = Path(__file__).parent

FASTQ_RECORD = "@read1\nACGT\n+\nIIII\n"


@pytest.fixture()
def fastq_file(tmp_path):
    """Write a small plain FASTQ file and return its path."""
    p = tmp_path / "test.fastq"
    p.write_text(FASTQ_RECORD * 10)  # 10 reads
    return p


@pytest.fixture()
def fastq_gz_file(tmp_path):
    """Write a small gzipped FASTQ file and return its path."""
    p = tmp_path / "test.fastq.gz"
    with gzip.open(p, "wt") as fh:
        fh.write(FASTQ_RECORD * 10)
    return p


@pytest.fixture()
def targets_tsv(tmp_path):
    """Write a minimal targets TSV and return its path."""
    p = tmp_path / "targets.tsv"
    p.write_text("chrom\tstart\tend\tname\nCHR1\t100\t200\tgene1\n")
    return p


@pytest.fixture()
def cgmlst_csv():
    """Return the path to the trimmed S. aureus cgMLST targets CSV (tab-separated)."""
    return TESTS_DIR / "Staphylococcus_aureus_cgMLST.csv"


@pytest.fixture()
def versions_yaml_a(tmp_path):
    p = tmp_path / "versions_a.yml"
    p.write_text("tool_a:\n  version: '1.0'\n")
    return p


@pytest.fixture()
def versions_yaml_b(tmp_path):
    p = tmp_path / "versions_b.yml"
    p.write_text("tool_b:\n  version: '2.0'\n")
    return p
