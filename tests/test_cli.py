"""Tests for the jasentool CLI."""
import json
import shutil
import subprocess
from pathlib import Path

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


def test_concatenated_versions_fixture(concatenated_versions):
    data = yaml.safe_load(concatenated_versions.read_text())
    # flatten: collect {software: version} across all process entries
    versions = {}
    for process_data in data.values():
        if isinstance(process_data, dict):
            for software, info in process_data.items():
                if isinstance(info, dict) and "version" in info:
                    versions[software] = info["version"]
    expected = {
        "amrfinderplus": "4.2.7",
        "chewbbaca": "3.5.2",
        "emmtyper": "0.2.0",
        "gambitcore": "0.0.2",
        "kleborate": "3.2.4",
        "bracken": "2.8",
        "mlst": "2.23.0",
        "mykrobe": "0.12.2",
        "nanoplot": "1.46.2",
        "quast": "5.2.0",
        "resfinder": "4.7.2",
        "samtools": "1.17",
        "sccmec": "1.2.0",
        "serotypefinder": "2.0.2",
        "shigapass": "1.5.0",
        "spatyper": "0.3.3",
        "tb-profiler": "6.7.0",
        "virulencefinder": "3.2.0",
    }
    for software, version in expected.items():
        assert versions.get(software) == version, f"unexpected version for {software}"


# ── module versions.yml heredoc rendering ───────────────────────────────────────
# JASEN nf modules emit versions.yml via `cat <<-END_VERSIONS`, where the body and
# terminator carry a leading TAB (stripped by `<<-`) and the YAML nesting itself uses
# spaces. These tests render that exact construct through bash and assert the result
# is tab-free, correctly-nested YAML that jasentool can parse.

# Leading whitespace below is a literal TAB followed by space-based YAML nesting.
_MODULE_HEREDOC = (
    "set -e\n"
    "cat <<-END_VERSIONS > {out}\n"
    "\tsamtools_stats:\n"
    "\t samtools:\n"
    "\t  version: 1.17\n"
    "\t  container: docker://clinicalgenomicslund/samtools:1.17\n"
    "\tEND_VERSIONS\n"
)


def _render_module_versions(tmp_path):
    """Render a module-style tab-indented heredoc via bash and return the output path."""
    out = tmp_path / "samtools_stats_versions.yml"
    script = tmp_path / "gen.sh"
    script.write_text(_MODULE_HEREDOC.format(out=out))
    subprocess.run(["bash", str(script)], check=True)
    return out


requires_bash = pytest.mark.skipif(shutil.which("bash") is None, reason="bash required")


@requires_bash
def test_module_heredoc_renders_tabfree_nested_yaml(tmp_path):
    out = _render_module_versions(tmp_path)
    text = out.read_text()
    assert "\t" not in text  # `<<-` stripped every leading tab; YAML keeps no tabs
    assert yaml.safe_load(text) == {
        "samtools_stats": {
            "samtools": {
                "version": 1.17,
                "container": "docker://clinicalgenomicslund/samtools:1.17",
            }
        }
    }


@requires_bash
def test_concatenate_files_parses_module_heredoc(tmp_path):
    out = _render_module_versions(tmp_path)
    merged = tmp_path / "versions.yml"
    result = runner.invoke(cli, ["concatenate-files", "-i", str(out), "-o", str(merged)])
    assert result.exit_code == 0, result.output
    data = yaml.safe_load(merged.read_text())
    assert data["samtools_stats"]["samtools"]["version"] == 1.17


@requires_bash
def test_create_yaml_parses_module_heredoc_versions(tmp_path):
    out = _render_module_versions(tmp_path)
    result = runner.invoke(cli, [
        "create-yaml",
        "--sample-id", "p1000",
        "--sample-name", "p1000",
        "--groups", "grpA",
        "--versions", str(out),
        "-o", str(tmp_path / "sample.yaml"),
    ])
    assert result.exit_code == 0, result.output


# ── create-yaml ────────────────────────────────────────────────────────────────

def test_create_yaml_minimal(tmp_path):
    out = tmp_path / "input.yml"
    result = runner.invoke(cli, [
        "create-yaml",
        "--sample-id", "SAMP001",
        "--sample-name", "Sample 001",
        "--groups", "group1",
        "-o", str(out),
    ])
    assert result.exit_code == 0, result.output
    data = yaml.safe_load(out.read_text())
    assert data["sample_id"] == "SAMP001"
    assert data["sample_name"] == "Sample 001"
    assert data["groups"] == ["group1"]
    assert data["igv_annotations"] == []
    assert data["analysis_result"] == []


def test_create_yaml_analysis_result(tmp_path):
    out = tmp_path / "input.yml"
    result = runner.invoke(cli, [
        "create-yaml",
        "--sample-id", "SAMP003",
        "--sample-name", "Sample 003",
        "--groups", "group1",
        "--plasmidfinder", "plasmidfinder.json",
        "--plasmidfinder-genome-hits", "plasmidfinder_hit_in_genome_seq.fsa",
        "--plasmidfinder-plasmid-seqs", "plasmidfinder_plasmid_seqs.fsa",
        "--resfinder", "resfinder.json",
        "--samtools", "samtools_coverage.txt",
        "--samtools-bedcov", "samtools_bedcov.txt",
        "--samtools-stats", "samtools_stats.txt",
        "--sccmec", "sccmec.tsv",
        "--shigatyper", "shigatyper.tsv",
        "--sourmash-signature", "sourmash.sig",
        "--ska-index", "index.skf",
        "-o", str(out),
    ])
    assert result.exit_code == 0, result.output
    data = yaml.safe_load(out.read_text())
    results = {(e["software"], e.get("subcommand")): e for e in data["analysis_result"]}
    assert results[("plasmidfinder", None)]["uri"] == "plasmidfinder.json"
    assert results[("plasmidfinder", "genome_hits")]["uri"] == "plasmidfinder_hit_in_genome_seq.fsa"
    assert results[("plasmidfinder", "plasmid_seqs")]["uri"] == "plasmidfinder_plasmid_seqs.fsa"
    assert results[("resfinder", None)]["uri"] == "resfinder.json"
    assert results[("samtools", "coverage")]["uri"] == "samtools_coverage.txt"
    assert results[("samtools", "bedcov")]["uri"] == "samtools_bedcov.txt"
    assert results[("samtools", "stats")]["uri"] == "samtools_stats.txt"
    assert results[("sccmectyper", None)]["uri"] == "sccmec.tsv"
    assert results[("shigatyper", None)]["uri"] == "shigatyper.tsv"
    assert data["index_artifacts"]["sourmash_signature"] == "sourmash.sig"
    assert data["index_artifacts"]["ska_index"] == "index.skf"


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


def test_create_yaml_all_args(tmp_path):
    out = tmp_path / "input.yml"
    result = runner.invoke(cli, [
        "create-yaml",
        "--sample-id", "SAMP004",
        "--sample-name", "Sample 004",
        "--lims-id", "LIMS123",
        "--groups", "group1",
        "--groups", "group2",
        "--amrfinder", "amrfinder.out",
        "--bam", "mapping.bam",
        "--bai", "mapping.bam.bai",
        "--chewbbaca", "chewbbaca.out",
        "--emmtyper", "emmtyper.tsv",
        "--gambitcore", "gambitcore.json",
        "--kleborate", "kleborate.tsv",
        "--kleborate-hamronization", "kleborate_hamronization.tsv",
        "--kraken", "kraken.out",
        "--mlst", "mlst.json",
        "--mykrobe", "mykrobe.json",
        "--nanoplot", "nanoplot.txt",
        "--nextflow-run-info", "analysis_meta.json",
        "--quast", "quast.tsv",
        "--ref-genome-sequence", "genome.fasta",
        "--ref-genome-annotation", "annotation.gff",
        "--resfinder", "resfinder.json",
        "--samtools", "samtools_coverage.txt",
        "--samtools-bedcov", "samtools_bedcov.txt",
        "--samtools-stats", "samtools_stats.txt",
        "--sccmec", "sccmec.tsv",
        "--serotypefinder", "serotypefinder.json",
        "--shigapass", "shigapass.tsv",
        "--ska-index", "index.skf",
        "--software-info", "resfinder_meta.json",
        "--software-info", "serotypefinder_meta.json",
        "--software-info", "virulencefinder_meta.json",
        "--sourmash-signature", "sourmash.sig",
        "--spatyper", "spatyper.tsv",
        "--tb-grading-rules-bed", "tb_grading_rules.bed",
        "--tbdb-bed", "tbdb.bed",
        "--tbprofiler", "tbprofiler.json",
        "--vcf", "variants.vcf",
        "--virulencefinder", "virulencefinder.json",
        "-o", str(out),
    ])
    assert result.exit_code == 0, result.output
    data = yaml.safe_load(out.read_text())

    # top-level fields
    assert data["sample_id"] == "SAMP004"
    assert data["sample_name"] == "Sample 004"
    assert data["lims_id"] == "LIMS123"
    assert data["groups"] == ["group1", "group2"]
    assert data["nextflow_run_info"] == "analysis_meta.json"
    assert data["ref_genome_sequence"] == "genome.fasta"
    assert data["ref_genome_annotation"] == "annotation.gff"
    assert data["software_info"] == [
        "resfinder_meta.json", "serotypefinder_meta.json", "virulencefinder_meta.json"
    ]

    # igv_annotations: bam/bai, tb_grading_rules_bed, tbdb_bed, vcf
    igv = {e["name"]: e for e in data["igv_annotations"]}
    assert igv["Read coverage"]["uri"] == "mapping.bam"
    assert igv["Read coverage"]["index_uri"] == "mapping.bam.bai"
    assert igv["tbdb grading rules bed"]["uri"] == "tb_grading_rules.bed"
    assert igv["tbdb bed"]["uri"] == "tbdb.bed"
    assert igv["Predicted variants"]["uri"] == "variants.vcf"

    # analysis_result entries
    results = {(e["software"], e.get("subcommand")): e for e in data["analysis_result"]}
    assert results[("amrfinder", None)]["uri"] == "amrfinder.out"
    assert results[("chewbbaca", None)]["uri"] == "chewbbaca.out"
    assert results[("emmtyper", None)]["uri"] == "emmtyper.tsv"
    assert results[("gambitcore", None)]["uri"] == "gambitcore.json"
    assert results[("kleborate", None)]["uri"] == "kleborate.tsv"
    assert results[("kleborate", "hamronization")]["uri"] == "kleborate_hamronization.tsv"
    assert results[("kraken", None)]["uri"] == "kraken.out"
    assert results[("mlst", None)]["uri"] == "mlst.json"
    assert results[("mykrobe", None)]["uri"] == "mykrobe.json"
    assert results[("nanoplot", None)]["uri"] == "nanoplot.txt"
    assert results[("quast", None)]["uri"] == "quast.tsv"
    assert results[("resfinder", None)]["uri"] == "resfinder.json"
    assert results[("samtools", "coverage")]["uri"] == "samtools_coverage.txt"
    assert results[("samtools", "bedcov")]["uri"] == "samtools_bedcov.txt"
    assert results[("samtools", "stats")]["uri"] == "samtools_stats.txt"
    assert results[("sccmectyper", None)]["uri"] == "sccmec.tsv"
    assert results[("serotypefinder", None)]["uri"] == "serotypefinder.json"
    assert results[("shigapass", None)]["uri"] == "shigapass.tsv"
    assert results[("spatyper", None)]["uri"] == "spatyper.tsv"
    assert results[("tbprofiler", None)]["uri"] == "tbprofiler.json"
    assert results[("virulencefinder", None)]["uri"] == "virulencefinder.json"

    # index_artifacts
    assert data["index_artifacts"]["sourmash_signature"] == "sourmash.sig"
    assert data["index_artifacts"]["ska_index"] == "index.skf"


def test_create_yaml_software_versions(tmp_path):
    versions_file = tmp_path / "versions.yml"
    versions_file.write_text(
        "JASEN:CALL_SCREENING:amrfinderplus:\n"
        " amrfinderplus:\n"
        "  version: 4.2.7\n"
        "  container: ncbi-amrfinderplus.sif\n"
        "JASEN:CALL_QUALITY_CONTROL:samtools:\n"
        " samtools:\n"
        "  version: 1.17\n"
        "  container: samtools.sif\n"
        "JASEN:CALL_RESISTANCE:resfinder:\n"
        " resfinder:\n"
        "  version: 4.7.2\n"
        "  container: resfinder.sif\n"
    )
    out = tmp_path / "input.yml"
    result = runner.invoke(cli, [
        "create-yaml",
        "--sample-id", "SAMP005",
        "--sample-name", "Sample 005",
        "--groups", "group1",
        "--amrfinder", "amrfinder.out",
        "--samtools", "samtools_coverage.txt",
        "--samtools-bedcov", "samtools_bedcov.txt",
        "--samtools-stats", "samtools_stats.txt",
        "--resfinder", "resfinder.json",
        "--spatyper", "spatyper.tsv",
        "--versions", str(versions_file),
        "-o", str(out),
    ])
    assert result.exit_code == 0, result.output
    data = yaml.safe_load(out.read_text())
    results = {(e["software"], e.get("subcommand")): e for e in data["analysis_result"]}

    # amrfinder maps to amrfinderplus in versions file
    assert results[("amrfinder", None)]["software_version"] == "4.2.7"
    # all samtools subcommands share the same version
    assert results[("samtools", "coverage")]["software_version"] == "1.17"
    assert results[("samtools", "bedcov")]["software_version"] == "1.17"
    assert results[("samtools", "stats")]["software_version"] == "1.17"
    assert results[("resfinder", None)]["software_version"] == "4.7.2"
    # spatyper has no version in the file
    assert "software_version" not in results[("spatyper", None)]
    assert "WARNING: no version found for software 'spatyper'" in result.output


def test_create_yaml_missing_required_args():
    result = runner.invoke(cli, ["create-yaml"])
    assert result.exit_code != 0


# ── format-cdm ─────────────────────────────────────────────────────────────────

def _write_cdm_manifest(tmp_path, fixtures_dir):
    for name in (
        "samtools_stats.txt",
        "samtools_bedcov.txt",
        "quast.tsv",
        "gambitcore.tsv",
        "chewbbaca.out",
        "analysis_meta.json",
    ):
        shutil.copy(fixtures_dir / name, tmp_path / name)

    manifest = tmp_path / "manifest.yml"
    manifest.write_text(
        """
sample_id: saureus_test_1
sample_name: saureus_test_1
lims_id: lims1
nextflow_run_info: ./analysis_meta.json
analysis_result:
  - software: samtools
    subcommand: stats
    software_version: "1.17"
    uri: ./samtools_stats.txt
  - software: samtools
    subcommand: bedcov
    software_version: "1.17"
    uri: ./samtools_bedcov.txt
  - software: quast
    software_version: "5.0"
    uri: ./quast.tsv
  - software: gambitcore
    software_version: "1.0"
    uri: ./gambitcore.tsv
  - software: chewbbaca
    software_version: "3.0"
    uri: ./chewbbaca.out
""",
        encoding="utf-8",
    )
    return manifest


def test_format_cdm(tmp_path):
    fixtures_dir = Path(__file__).parent / "fixtures" / "cdm"
    manifest = _write_cdm_manifest(tmp_path, fixtures_dir)
    out = tmp_path / "cdm_input.json"

    result = runner.invoke(cli, ["format-cdm", str(manifest), "-o", str(out)])

    assert result.exit_code == 0, result.output
    records = json.loads(out.read_text())
    ids = {r["id"] for r in records}
    assert ids == {"postalignqc", "quast", "gambitcore", "chewbbaca_missing_loci"}


def test_format_cdm_missing_manifest():
    result = runner.invoke(cli, ["format-cdm", "does_not_exist.yml"])
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


# ── compare-distances ───────────────────────────────────────────────────────────

def _write_tsv(path, rows):
    path.write_text("\n".join("\t".join(map(str, row)) for row in rows) + "\n")


def test_compare_distances(tmp_path):
    import pandas as pd

    f1 = tmp_path / "file1.tsv"
    f2 = tmp_path / "file2.tsv"
    _write_tsv(f1, [
        ["FILE", "loc1", "loc2", "loc3"],
        ["s1", 1, 2, 3],
        ["s2", 1, 2, 4],
        ["s3", 5, 2, 3],
    ])
    _write_tsv(f2, [
        ["FILE", "loc1", "loc2", "loc3"],
        ["s1", 1, 2, 3],
        ["s2", 1, 2, 3],
        ["s3", 5, 2, 3],
    ])
    out = tmp_path / "out"
    result = runner.invoke(cli, [
        "compare-distances", "-i", str(f1), str(f2), "-o", str(out),
    ])
    assert result.exit_code == 0, result.output

    m1 = pd.read_csv(out / "file1_distance_matrix.tsv", sep="\t", index_col=0)
    m2 = pd.read_csv(out / "file2_distance_matrix.tsv", sep="\t", index_col=0)
    diff = pd.read_csv(out / "file1_vs_file2_diff_matrix.tsv", sep="\t", index_col=0)

    # distance = number of mismatching loci
    assert m1.loc["s2", "s3"] == 2
    assert m1.loc["s1", "s2"] == 1
    assert m1.loc["s1", "s1"] == 0
    assert m2.loc["s1", "s2"] == 0
    # diff = matrix1 - matrix2
    assert diff.loc["s2", "s3"] == 1
    assert diff.loc["s1", "s3"] == 0

    # identical sample sets -> missing-samples report is header-only
    missing = (out / "file1_vs_file2_missing_samples.tsv").read_text().splitlines()
    assert missing == ["sample_id\tpresent_in\tmissing_from"]


def test_compare_distances_excludes_missing_samples(tmp_path):
    import pandas as pd

    f1 = tmp_path / "file1.tsv"
    f2 = tmp_path / "file2.tsv"
    # s3 is only in file1; comparison should still run over the shared s1/s2.
    _write_tsv(f1, [
        ["FILE", "loc1", "loc2"],
        ["s1", 1, 2],
        ["s2", 1, 3],
        ["s3", 9, 9],
    ])
    _write_tsv(f2, [
        ["FILE", "loc1", "loc2"],
        ["s1", 1, 2],
        ["s2", 1, 4],
    ])
    out = tmp_path / "out"
    result = runner.invoke(cli, [
        "compare-distances", "-i", str(f1), str(f2), "-o", str(out),
    ])
    assert result.exit_code == 0, result.output

    diff = pd.read_csv(out / "file1_vs_file2_diff_matrix.tsv", sep="\t", index_col=0)
    assert list(diff.index) == ["s1", "s2"]  # s3 excluded
    assert "s3" not in diff.columns

    rows = [r.split("\t") for r in
            (out / "file1_vs_file2_missing_samples.tsv").read_text().splitlines()]
    assert rows[0] == ["sample_id", "present_in", "missing_from"]
    assert ["s3", "file1.tsv", "file2.tsv"] in rows[1:]


def test_compare_distances_drops_st_and_handles_old_header(tmp_path):
    import pandas as pd

    old = tmp_path / "old.tsv"   # older chewBBACA: #Name, ST, loci...
    new = tmp_path / "new.tsv"   # newer chewBBACA: FILE, loci...
    # s1/s2 share both loci but have different ST; if ST were NOT dropped it would
    # show up as a mismatch (distance 1) instead of 0.
    _write_tsv(old, [
        ["#Name", "ST", "loc1", "loc2"],
        ["s1", 10, 1, 2],
        ["s2", 20, 1, 2],
    ])
    _write_tsv(new, [
        ["FILE", "loc1", "loc2"],
        ["s1", 1, 2],
        ["s2", 1, 3],
    ])
    out = tmp_path / "out"
    result = runner.invoke(cli, [
        "compare-distances", "-i", str(old), str(new), "-o", str(out),
    ])
    assert result.exit_code == 0, result.output

    m_old = pd.read_csv(out / "old_distance_matrix.tsv", sep="\t", index_col=0)
    m_new = pd.read_csv(out / "new_distance_matrix.tsv", sep="\t", index_col=0)
    # ST dropped -> s1 vs s2 identical across loci -> distance 0
    assert m_old.loc["s1", "s2"] == 0
    # cross-format comparison still works positionally
    assert m_new.loc["s1", "s2"] == 1


def test_compare_distances_dash_control(tmp_path):
    import pandas as pd

    f1 = tmp_path / "file1.tsv"
    f2 = tmp_path / "file2.tsv"
    # file1: loc3 is an error code (LNF) in s2 -> missing (broader than just "-").
    _write_tsv(f1, [
        ["FILE", "loc1", "loc2", "loc3"],
        ["s1", 1, 3, 5],
        ["s2", 1, 4, "LNF"],
    ])
    # file2: no missing data, so loc3 is comparable there.
    _write_tsv(f2, [
        ["FILE", "loc1", "loc2", "loc3"],
        ["s1", 1, 3, 5],
        ["s2", 1, 4, 5],
    ])
    out = tmp_path / "out"
    result = runner.invoke(cli, [
        "compare-distances", "-i", str(f1), str(f2), "-o", str(out),
    ])
    assert result.exit_code == 0, result.output

    diff = pd.read_csv(out / "file1_vs_file2_diff_matrix.tsv", sep="\t", index_col=0)
    abs_diff = pd.read_csv(out / "file1_vs_file2_abs_diff_matrix.tsv", sep="\t", index_col=0)
    dash_change = pd.read_csv(out / "file1_vs_file2_dash_change_matrix.tsv", sep="\t", index_col=0)
    unexplained = pd.read_csv(out / "file1_vs_file2_unexplained_matrix.tsv", sep="\t", index_col=0)

    # both files have 1 mismatch (loc2) -> diff 0; loc3 comparable only in file2
    # (LNF counts as missing -> proves the broader definition, not just "-")
    assert diff.loc["s1", "s2"] == 0
    assert abs_diff.loc["s1", "s2"] == 0
    assert dash_change.loc["s1", "s2"] == 1   # symmetric
    assert dash_change.loc["s2", "s1"] == 1
    # |diff| (0) <= dash_change (1) -> fully attributable to missing data
    assert unexplained.loc["s1", "s2"] == 0


def test_compare_distances_missing_loci_per_sample(tmp_path):
    f1 = tmp_path / "file1.tsv"
    f2 = tmp_path / "file2.tsv"
    # missing = non-integer except INF-<n> (which counts as allele <n>)
    _write_tsv(f1, [
        ["FILE", "loc1", "loc2", "loc3", "loc4"],
        ["s1", 1, "-", "LNF", "INF-5"],   # missing: loc2, loc3 (INF-5 is NOT missing) = 2
        ["s2", 1, 4, 5, 6],               # 0 missing
    ])
    _write_tsv(f2, [
        ["FILE", "loc1", "loc2", "loc3", "loc4"],
        ["s1", 1, 2, "PLOT3", 5],         # missing: loc3 = 1
        ["s2", 1, 4, 5, 6],               # 0 missing
    ])
    out = tmp_path / "out"
    result = runner.invoke(cli, [
        "compare-distances", "-i", str(f1), str(f2), "-o", str(out),
    ])
    assert result.exit_code == 0, result.output

    rows = [r.split("\t") for r in
            (out / "file1_vs_file2_missing_loci_per_sample.tsv").read_text().splitlines()]
    assert rows[0] == ["sample_id", "n_missing_file1", "n_missing_file2", "delta"]
    body = {r[0]: r[1:] for r in rows[1:]}
    assert body["s1"] == ["2", "1", "1"]   # 2 missing in file1, 1 in file2, delta 1
    assert body["s2"] == ["0", "0", "0"]


def test_compare_distances_matrices_are_sorted(tmp_path):
    import pandas as pd

    f1 = tmp_path / "file1.tsv"
    f2 = tmp_path / "file2.tsv"
    # rows out of order; output matrices should be sorted by sample id
    _write_tsv(f1, [
        ["FILE", "loc1", "loc2"],
        ["s3", 1, 2],
        ["s1", 1, 2],
        ["s2", 1, 3],
    ])
    _write_tsv(f2, [
        ["FILE", "loc1", "loc2"],
        ["s2", 1, 2],
        ["s3", 1, 2],
        ["s1", 1, 2],
    ])
    out = tmp_path / "out"
    result = runner.invoke(cli, [
        "compare-distances", "-i", str(f1), str(f2), "-o", str(out),
    ])
    assert result.exit_code == 0, result.output

    for name in ("file1_distance_matrix.tsv", "file2_distance_matrix.tsv",
                 "file1_vs_file2_diff_matrix.tsv"):
        m = pd.read_csv(out / name, sep="\t", index_col=0)
        assert list(m.index) == ["s1", "s2", "s3"]
        assert list(m.columns) == ["s1", "s2", "s3"]


def test_compare_distances_errors_without_header(tmp_path):
    f1 = tmp_path / "file1.tsv"
    f2 = tmp_path / "file2.tsv"
    # No header row (first cell is a sample id, not FILE/#Name) -> error.
    _write_tsv(f1, [["s1", 1, 2], ["s2", 1, 3]])
    _write_tsv(f2, [["FILE", "loc1", "loc2"], ["s1", 1, 2], ["s2", 1, 3]])
    out = tmp_path / "out"
    result = runner.invoke(cli, [
        "compare-distances", "-i", str(f1), str(f2), "-o", str(out),
    ])
    assert result.exit_code != 0


def test_compare_distances_uses_cgmlst_dists(monkeypatch, tmp_path):
    import pandas as pd

    # Fake cgmlst-dists output; values differ from what the alleles imply (all
    # identical -> Python fallback would be 0), proving the cgmlst-dists path was used.
    matrix_text = "cgmlst-dists\ts1\ts2\ts3\ns1\t0\t5\t7\ns2\t5\t0\t9\ns3\t7\t9\t0\n"

    class FakeProc:
        stdout = matrix_text
        stderr = ""
        returncode = 0

    calls = []

    def fake_run(cmd, *a, **k):
        calls.append(cmd)
        return FakeProc()

    monkeypatch.setattr("jasentool.compare_distances.subprocess.run", fake_run)

    rows = [["FILE", "loc1", "loc2"], ["s1", 1, 1], ["s2", 1, 1], ["s3", 1, 1]]
    f1, f2 = tmp_path / "file1.tsv", tmp_path / "file2.tsv"
    _write_tsv(f1, rows)
    _write_tsv(f2, rows)
    out = tmp_path / "out"
    result = runner.invoke(cli, ["compare-distances", "-i", str(f1), str(f2), "-o", str(out)])
    assert result.exit_code == 0, result.output

    m1 = pd.read_csv(out / "file1_distance_matrix.tsv", sep="\t", index_col=0)
    assert m1.loc["s1", "s2"] == 5
    assert m1.loc["s2", "s3"] == 9
    assert (out / "file1_clean.tsv").exists()   # preprocessed input fed to cgmlst-dists
    # distance cap raised so large distances aren't clamped to the 999 default
    assert ["-x", "2000"] == calls[0][1:3]


def test_compare_distances_plots(tmp_path):
    f1, f2 = tmp_path / "file1.tsv", tmp_path / "file2.tsv"
    _write_tsv(f1, [["FILE", "loc1", "loc2"], ["s1", 1, 2], ["s2", 1, 3], ["s3", 4, 5]])
    _write_tsv(f2, [["FILE", "loc1", "loc2"], ["s1", 1, 2], ["s2", 1, 4], ["s3", 6, 5]])
    st = tmp_path / "st.csv"
    st.write_text("sample_name,mlst_st\ns1,1\ns2,1\ns3,22\n")
    out = tmp_path / "out"
    result = runner.invoke(cli, [
        "compare-distances", "-i", str(f1), str(f2), "-o", str(out), "--mlst", str(st),
    ])
    assert result.exit_code == 0, result.output
    assert (out / "file1_vs_file2_distance_scatter.png").exists()
    assert (out / "file1_vs_file2_bland_altman.png").exists()
    assert (out / "file1_vs_file2_missing_vs_st.png").exists()


def test_compare_distances_bland_altman_zoom(tmp_path):
    """--max-mean-distance/--min-mean-distance write an extra zoomed Bland-Altman
    alongside the full-range one."""
    f1, f2 = tmp_path / "file1.tsv", tmp_path / "file2.tsv"
    _write_tsv(f1, [["FILE", "loc1", "loc2"], ["s1", 1, 2], ["s2", 1, 3], ["s3", 4, 5]])
    _write_tsv(f2, [["FILE", "loc1", "loc2"], ["s1", 1, 2], ["s2", 1, 4], ["s3", 6, 5]])
    out = tmp_path / "out"
    result = runner.invoke(cli, [
        "compare-distances", "-i", str(f1), str(f2), "-o", str(out),
        "--min-mean-distance", "0", "--max-mean-distance", "100",
    ])
    assert result.exit_code == 0, result.output
    # full-range plot still written
    assert (out / "file1_vs_file2_bland_altman.png").exists()
    # extra zoomed plot written alongside it, named by its mean-distance window
    assert (out / "file1_vs_file2_bland_altman_mean_0-100.png").exists()


def test_compare_distances_no_zoom_by_default(tmp_path):
    """Without the bounds flags, no zoomed Bland-Altman is produced."""
    f1, f2 = tmp_path / "file1.tsv", tmp_path / "file2.tsv"
    _write_tsv(f1, [["FILE", "loc1", "loc2"], ["s1", 1, 2], ["s2", 1, 3], ["s3", 4, 5]])
    _write_tsv(f2, [["FILE", "loc1", "loc2"], ["s1", 1, 2], ["s2", 1, 4], ["s3", 6, 5]])
    out = tmp_path / "out"
    result = runner.invoke(cli, [
        "compare-distances", "-i", str(f1), str(f2), "-o", str(out),
    ])
    assert result.exit_code == 0, result.output
    zoomed = list(out.glob("*_bland_altman_mean_*.png"))
    assert zoomed == []


def test_compare_distances_verbose_points(tmp_path):
    import pandas as pd

    f1, f2 = tmp_path / "file1.tsv", tmp_path / "file2.tsv"
    _write_tsv(f1, [["FILE", "loc1", "loc2"], ["s1", 1, 2], ["s2", 1, 3], ["s3", 4, 5]])
    _write_tsv(f2, [["FILE", "loc1", "loc2"], ["s1", 1, 2], ["s2", 1, 4], ["s3", 6, 5]])
    st = tmp_path / "st.csv"
    st.write_text("sample_name,mlst_st\ns1,1\ns2,1\ns3,22\n")
    out = tmp_path / "out"
    result = runner.invoke(cli, [
        "compare-distances", "-i", str(f1), str(f2), "-o", str(out), "--mlst", str(st), "-v",
    ])
    assert result.exit_code == 0, result.output

    pts = pd.read_csv(out / "file1_vs_file2_distance_points.tsv", sep="\t")
    assert len(pts) == 3   # 3 shared samples -> 3 upper-triangle pairs
    row = pts[(pts.sample_a == "s1") & (pts.sample_b == "s2")].iloc[0]
    assert row["file1_distance"] == 1 and row["file2_distance"] == 1 and row["diff"] == 0
    assert (out / "file1_vs_file2_missing_vs_st_points.tsv").exists()


def test_compare_distances_help():
    result = runner.invoke(cli, ["compare-distances", "--help"])
    assert result.exit_code == 0


def test_compare_distances_missing_args():
    result = runner.invoke(cli, ["compare-distances"])
    assert result.exit_code != 0
