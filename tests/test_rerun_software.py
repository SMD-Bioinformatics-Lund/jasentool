import csv
import json
import os

import pytest
from click.testing import CliRunner

from jasentool.check_backup import _collect_assemblies
from jasentool.cli import cli

runner = CliRunner()


class FakeTool:
    """Stands in for subprocess.run: records each command and writes the tool's outputs."""

    def __init__(self, returncode=0, writes=None):
        self.calls = []
        self.returncode = returncode
        self.writes = writes or []

    def __call__(self, cmd, cwd=None, **kwargs):
        self.calls.append({"cmd": cmd, "cwd": cwd})
        if cwd and self.returncode == 0:
            sample_id = os.path.basename(cwd)
            for name in self.writes:
                with open(os.path.join(cwd, name.format(sid=sample_id)), "w") as fout:
                    fout.write("result\n")

        class Proc:
            returncode = self.returncode
        return Proc()


def _install(monkeypatch, fake):
    monkeypatch.setattr("jasentool.rerun_software.subprocess.run", fake)
    return fake


def _csv(path, rows):
    with open(path, "w", newline="") as fout:
        writer = csv.DictWriter(fout, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return path


def _touch(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(">x\nACGT\n")
    return path


def _samplesheet(tmp_path, platform="illumina", paired=True):
    r1 = _touch(tmp_path / "reads" / "s1_R1.fastq.gz")
    row = {"id": "s1", "platform": platform, "read1": str(r1), "read2": ""}
    if paired:
        row["read2"] = str(_touch(tmp_path / "reads" / "s1_R2.fastq.gz"))
    return _csv(tmp_path / "samplesheet.csv", [row])


def _invoke(*args):
    return runner.invoke(cli, ["rerun-software", *map(str, args)])


def test_chewbbaca_runs_one_batch_in_singularity(monkeypatch, tmp_path):
    fake = _install(monkeypatch, FakeTool())
    a1, a2 = _touch(tmp_path / "s1_mask.fasta"), _touch(tmp_path / "s2_mask.fasta")
    masked = _csv(tmp_path / "masked.csv", [
        {"sample_id": "s1", "profile": "escherichia_coli", "masked_assembly_path": str(a1)},
        {"sample_id": "s2", "profile": "klebsiella", "masked_assembly_path": str(a2)},
    ])
    schema = tmp_path / "schema"
    schema.mkdir()
    image = _touch(tmp_path / "chewbbaca.sif")

    result = _invoke("--tool", "chewbbaca", "-i", masked, "-o", tmp_path / "out", "--db", schema,
                     "--profile", "escherichia_coli", "--singularity-image", image,
                     "--singularity-bind", "/data")

    assert result.exit_code == 0, result.output
    cmd = fake.calls[0]["cmd"]
    assert cmd[:5] == ["singularity", "exec", "--bind", "/data", str(image)]
    assert cmd[5:7] == ["chewie", "AlleleCall"]
    assert cmd[cmd.index("--schema-directory") + 1] == str(schema)
    assert (tmp_path / "out" / "batch_input.list").read_text().splitlines() == [str(a1)]


def test_chewbbaca_passes_through_its_exit_code(monkeypatch, tmp_path):
    _install(monkeypatch, FakeTool(returncode=3))
    a1 = _touch(tmp_path / "s1_mask.fasta")
    masked = _csv(tmp_path / "masked.csv", [{"sample_id": "s1", "masked_assembly_path": str(a1)}])
    schema = tmp_path / "schema"
    schema.mkdir()

    result = _invoke("--tool", "chewbbaca", "-i", masked, "-o", tmp_path / "out", "--db", schema)

    assert result.exit_code == 3


def test_old_rerun_chewbbaca_name_still_works(monkeypatch, tmp_path):
    fake = _install(monkeypatch, FakeTool())
    a1 = _touch(tmp_path / "s1_mask.fasta")
    masked = _csv(tmp_path / "masked.csv", [{"sample_id": "s1", "masked_assembly_path": str(a1)}])
    schema = tmp_path / "schema"
    schema.mkdir()

    result = runner.invoke(cli, ["rerun-chewbbaca", "--masked-assemblies", str(masked),
                                 "--schema-dir", str(schema), "--output-dir", str(tmp_path / "out")])

    assert result.exit_code == 0, result.output
    assert fake.calls[0]["cmd"][:2] == ["chewie", "AlleleCall"]


@pytest.mark.parametrize("profile, organism", [
    ("escherichia_coli", "Escherichia"),
    ("staphylococcus_aureus", "Staphylococcus_aureus"),
    ("streptococcus", None),
])
def test_amrfinder_runs_per_sample_with_jasen_organism(monkeypatch, tmp_path, profile, organism):
    fake = _install(monkeypatch, FakeTool(writes=["{sid}_amrfinder.tsv"]))
    assembly = _touch(tmp_path / "fasta" / "s1_spades.fasta")
    assemblies = _csv(tmp_path / "assemblies.csv", [
        {"sample_id": "s1", "profile": profile, "assembly_path": str(assembly)},
    ])
    out = tmp_path / "out"

    result = _invoke("--tool", "amrfinder", "-i", assemblies, "-o", out, "--profile", profile)

    assert result.exit_code == 0, result.output
    cmd = fake.calls[0]["cmd"]
    assert cmd[:4] == ["amrfinder", "--nucleotide", str(assembly), "--plus"]
    assert (cmd[cmd.index("--organism") + 1] if "--organism" in cmd else None) == organism
    assert (out / "s1_amrfinder.tsv").exists()
    assert not (out / "work" / "s1").exists()


def test_resfinder_matches_jasen_arguments_and_outputs(monkeypatch, tmp_path):
    fake = _install(monkeypatch, FakeTool(writes=["{sid}_resfinder.json", "pheno_table.txt"]))
    resfinder_db, pointfinder_db = tmp_path / "resfinder_db", tmp_path / "pointfinder_db"
    resfinder_db.mkdir()
    pointfinder_db.mkdir()
    (resfinder_db / "VERSION").write_text("2.4.0\r\n")
    out = tmp_path / "out"

    result = _invoke("--tool", "resfinder", "-i", _samplesheet(tmp_path, platform="nanopore"),
                     "-o", out, "--profile", "escherichia_coli",
                     "--db", resfinder_db, "--pointfinder-db", pointfinder_db)

    assert result.exit_code == 0, result.output
    cmd = fake.calls[0]["cmd"]
    assert cmd[:3] == ["python", "-m", "resfinder"]
    assert cmd[cmd.index("--species") + 1] == "escherichia coli"
    assert cmd[-3:] == ["--nanopore", "--ignore_indels", "--ignore_stop_codons"]
    assert (out / "s1_resfinder.json").exists()
    assert (out / "s1_pheno_table.txt").exists()
    assert not (out / "s1_point_table.txt").exists()
    assert json.loads((out / "s1_resfinder_meta.json").read_text()) == [
        {"name": "resfinder", "version": "2.4.0", "type": "database"},
        {"name": "pointfinder", "version": "unknown", "type": "database"},
    ]


@pytest.mark.parametrize("platform, paired, expected", [
    ("illumina", True, ["--R1", "--R2"]),
    ("illumina", False, ["--SE"]),
    ("nanopore", False, ["--SE", "--ont"]),
])
def test_shigatyper_read_arguments(monkeypatch, tmp_path, platform, paired, expected):
    fake = _install(monkeypatch, FakeTool(writes=["{sid}.tsv", "{sid}-hits.tsv"]))
    out = tmp_path / "out"

    result = _invoke("--tool", "shigatyper", "-i", _samplesheet(tmp_path, platform, paired),
                     "-o", out, "--jobs", 2)

    assert result.exit_code == 0, result.output
    cmd = fake.calls[0]["cmd"]
    assert [arg for arg in cmd if arg.startswith("--")] == expected + ["--name"]
    assert cmd[-1] == "s1"
    assert (out / "s1.tsv").exists() and (out / "s1-hits.tsv").exists()


def test_failed_sample_keeps_work_dir_and_exits_nonzero(monkeypatch, tmp_path):
    _install(monkeypatch, FakeTool(returncode=1))
    out = tmp_path / "out"

    result = _invoke("--tool", "shigatyper", "-i", _samplesheet(tmp_path), "-o", out)

    assert result.exit_code == 1
    assert (out / "work" / "s1" / "shigatyper.log").exists()


def test_samples_with_missing_inputs_are_skipped(monkeypatch, tmp_path):
    fake = _install(monkeypatch, FakeTool(writes=["{sid}.tsv"]))
    r1 = _touch(tmp_path / "s1_R1.fastq.gz")
    sheet = _csv(tmp_path / "sheet.csv", [
        {"id": "s1", "platform": "illumina", "read1": str(r1), "read2": ""},
        {"id": "s2", "platform": "illumina", "read1": str(tmp_path / "gone.fastq.gz"), "read2": ""},
    ])

    result = _invoke("--tool", "shigatyper", "-i", sheet, "-o", tmp_path / "out")

    assert result.exit_code == 0, result.output
    assert [call["cmd"][-1] for call in fake.calls] == ["s1"]


@pytest.mark.parametrize("args, message", [
    (["--tool", "resfinder", "--profile", "escherichia_coli", "--db", "x"],
     "requires --pointfinder-db"),
    (["--tool", "amrfinder"], "requires --profile"),
    (["--tool", "amrfinder", "--profile", "escherichia_coli", "--training-file", "x"],
     "--training-file is not used"),
    (["--tool", "shigatyper", "--db", "x"], "--db is not used"),
    (["--tool", "chewbbaca", "--db", "x", "--jobs", "2"], "--jobs is not used"),
])
def test_tool_specific_options_are_checked(tmp_path, args, message):
    result = _invoke(*args, "-i", tmp_path / "in.csv", "-o", tmp_path / "out")

    assert result.exit_code == 2
    assert message in result.output


def test_collect_assemblies_picks_jasen_final_assembly(tmp_path):
    fasta = tmp_path / "ecoli" / "fasta"
    for name in ("s1_flye.fasta", "s1_medaka.fasta", "s2_skesa.fasta", "s3_flye.fasta"):
        _touch(fasta / name)
    samples = [{"sample_id": sid, "sample_name": f"name_{sid}"} for sid in ("s1", "s2", "s3")]

    rows = _collect_assemblies(samples, str(tmp_path), "ecoli", "escherichia_coli")

    assert [(r["sample_id"], os.path.basename(r["assembly_path"])) for r in rows] == [
        ("s1", "s1_medaka.fasta"), ("s2", "s2_skesa.fasta"),
    ]
