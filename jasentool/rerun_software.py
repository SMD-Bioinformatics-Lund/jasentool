"""Re-run a JASEN tool on backed-up inputs listed in a CSV.

- chewbbaca: `<stem>_masked_assemblies.csv` from `check-backup`. One `chewie AlleleCall`
  over the whole batch, as JASEN runs it.
- amrfinder: `<stem>_assemblies.csv` from `check-backup`. One `amrfinder --plus` per sample.
- resfinder, shigatyper: a JASEN samplesheet (`id`, `platform`, `read1`, `read2`). One run
  per sample on the reads it lists.

Arguments and output file names follow JASEN's modules, so the results can sit alongside
the backed-up ones. Per-sample tools run in `<output-dir>/work/<sample_id>/`, which is
removed after a successful run and kept, with the tool's log, after a failed one.
"""

import csv
import json
import os
import shlex
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

from jasentool.log import get_logger

logger = get_logger(__name__)

RERUN_TOOLS = ("amrfinder", "chewbbaca", "resfinder", "shigatyper")

_DEFAULT_BIN = {
    "amrfinder": "amrfinder",
    "chewbbaca": "chewie",
    "resfinder": "python -m resfinder",
    "shigatyper": "shigatyper",
}

_INPUT_COLUMNS = {
    "amrfinder": ["assembly_path"],
    "chewbbaca": ["masked_assembly_path"],
    "resfinder": ["read1"],
    "shigatyper": ["read1"],
}
_PATH_COLUMNS = ["assembly_path", "masked_assembly_path", "read1", "read2"]


def _jasen_species(profile):
    """JASEN's params.species for a profile, e.g. escherichia_coli -> 'escherichia coli'."""
    return profile.replace("_", " ") if profile else None


def _amrfinder_organism(species):
    """AMRFinderPlus --organism for a JASEN species, as JASEN's get_species_taxon_name."""
    if species == "escherichia coli":
        return "Escherichia"
    names = (species or "").split()
    if len(names) < 2:
        return None
    return f"{names[0].capitalize()}_{names[1]}"


def _resfinder_species(species):
    """ResFinder --species for a JASEN species, as JASEN's check_taxon."""
    if species in {"staphylococcus", "streptococcus", "streptococcus pyogenes"}:
        return "Other"
    return species


def _is_nanopore(row):
    return (row.get("platform") or "").strip().lower() == "nanopore"


class RerunSoftware:
    """Run one supported tool over every sample in an input CSV."""

    def __init__(self, options):
        self.options = options
        self.tool = options.tool
        self.output_dir = os.path.abspath(options.output_dir)
        self.species = _jasen_species(options.profile)

    def run(self):
        """Validate inputs, then run the tool as a batch (chewbbaca) or per sample."""
        self._validate()
        rows = self._read_rows()
        if not rows:
            logger.error("No samples to process in %s", self.options.input)
            sys.exit(1)
        os.makedirs(self.output_dir, exist_ok=True)
        if self.tool == "chewbbaca":
            sys.exit(self._run_chewbbaca(rows))
        self._run_per_sample(rows)

    def _validate(self):
        checks = [
            ("--input", self.options.input, os.path.isfile),
            ("--db", self.options.db, os.path.isdir),
            ("--pointfinder-db", self.options.pointfinder_db, os.path.isdir),
            ("--training-file", self.options.training_file, os.path.isfile),
            ("--singularity-image", self.options.singularity_image, os.path.isfile),
        ]
        for flag, path, exists in checks:
            if path and not exists(path):
                logger.error("%s not found: %s", flag, path)
                sys.exit(1)

    def _read_rows(self):
        """Rows to run, keyed by `sample_id`, filtered by profile and to existing inputs."""
        with open(self.options.input, newline="", encoding="utf-8") as fin:
            reader = csv.DictReader(fin)
            fields = reader.fieldnames or []
            id_column = "sample_id" if "sample_id" in fields else "id"
            missing = [col for col in [id_column] + _INPUT_COLUMNS[self.tool] if col not in fields]
            if missing:
                logger.error("%s has no %s column(s)", self.options.input, ", ".join(missing))
                sys.exit(1)
            rows = list(reader)

        if self.options.profile and "profile" in fields:
            kept = [row for row in rows if row.get("profile") == self.options.profile]
            if len(kept) < len(rows):
                logger.info("Skipped %d rows from other profiles", len(rows) - len(kept))
            rows = kept

        selected = {}
        for row in rows:
            sample_id = (row.get(id_column) or "").strip()
            if not sample_id:
                continue
            if sample_id in selected:
                logger.warning("Duplicate sample %s in %s; using its first row",
                               sample_id, self.options.input)
                continue
            paths = {col: os.path.abspath(row[col]) for col in _PATH_COLUMNS if row.get(col)}
            absent = [path for path in paths.values() if not os.path.isfile(path)]
            if absent:
                logger.warning("%s: input not found, skipping: %s", sample_id, ", ".join(absent))
                continue
            selected[sample_id] = {**row, **paths, "sample_id": sample_id}
        return list(selected.values())

    def _command(self, args):
        cmd = []
        if self.options.singularity_image:
            cmd.extend(["singularity", "exec"])
            if self.options.singularity_bind:
                cmd.extend(["--bind", self.options.singularity_bind])
            cmd.append(self.options.singularity_image)
        cmd.extend(shlex.split(self.options.bin or _DEFAULT_BIN[self.tool]))
        return cmd + args

    def _run_chewbbaca(self, rows):
        batch_list = os.path.join(self.output_dir, "batch_input.list")
        with open(batch_list, "w", encoding="utf-8") as fout:
            for row in rows:
                fout.write(f"{row['masked_assembly_path']}\n")
        logger.info("Wrote %d paths to %s", len(rows), batch_list)
        args = [
            "AlleleCall",
            "-i", batch_list,
            "--cpu", str(self.options.cpus),
            "--output-directory", os.path.join(self.output_dir, "output_dir"),
            "--schema-directory", os.path.abspath(self.options.db),
        ]
        if self.options.training_file:
            args.extend(["--ptf", os.path.abspath(self.options.training_file)])
        cmd = self._command(args)
        logger.info("Running: %s", " ".join(cmd))
        return subprocess.run(cmd, check=False).returncode

    def _run_per_sample(self, rows):
        build = {
            "amrfinder": self._amrfinder_args,
            "resfinder": self._resfinder_args,
            "shigatyper": self._shigatyper_args,
        }[self.tool]
        with ThreadPoolExecutor(max_workers=self.options.jobs) as pool:
            succeeded = list(pool.map(lambda row: self._run_sample(row, build), rows))
        failed = [row["sample_id"] for row, ok in zip(rows, succeeded) if not ok]
        logger.info("%s finished: %d succeeded, %d failed",
                    self.tool, len(rows) - len(failed), len(failed))
        if failed:
            logger.error("Failed samples (work dirs kept under %s): %s",
                         os.path.join(self.output_dir, "work"), ", ".join(failed))
            sys.exit(1)

    def _run_sample(self, row, build):
        """Run one sample in its work dir, then move its outputs into the output dir."""
        sample_id = row["sample_id"]
        work_dir = os.path.join(self.output_dir, "work", sample_id)
        os.makedirs(work_dir, exist_ok=True)
        args, outputs = build(row, work_dir)
        cmd = self._command(args)
        log_path = os.path.join(work_dir, f"{self.tool}.log")
        logger.info("%s: running %s", sample_id, " ".join(cmd))
        with open(log_path, "w", encoding="utf-8") as log:
            returncode = subprocess.run(
                cmd, cwd=work_dir, stdout=log, stderr=subprocess.STDOUT, check=False,
            ).returncode
        if returncode != 0:
            logger.error("%s: %s exited with %d; see %s", sample_id, self.tool, returncode, log_path)
            return False
        for name, dest_name, required in outputs:
            src = os.path.join(work_dir, name)
            if os.path.isfile(src):
                shutil.move(src, os.path.join(self.output_dir, dest_name))
            elif required:
                logger.error("%s: %s wrote no %s; see %s", sample_id, self.tool, name, log_path)
                return False
        shutil.rmtree(work_dir)
        return True

    def _amrfinder_args(self, row, work_dir):
        output = f"{row['sample_id']}_amrfinder.tsv"
        args = ["--nucleotide", row["assembly_path"], "--plus",
                "--threads", str(self.options.cpus), "--output", output]
        if self.options.db:
            args.extend(["--database", os.path.abspath(self.options.db)])
        organism = _amrfinder_organism(self.species)
        if organism:
            args.extend(["--organism", organism])
        return args, [(output, output, True)]

    def _resfinder_args(self, row, work_dir):
        sample_id = row["sample_id"]
        reads = [row["read1"]] + ([row["read2"]] if row.get("read2") else [])
        meta = f"{sample_id}_resfinder_meta.json"
        self._write_resfinder_meta(os.path.join(work_dir, meta))
        args = [
            "--inputfastq", *reads,
            "--species", _resfinder_species(self.species),
            "--acquired", "--db_path_res", os.path.abspath(self.options.db),
            "--point", "--db_path_point", os.path.abspath(self.options.pointfinder_db),
            "--out_json", f"{sample_id}_resfinder.json",
            "--outputPath", ".",
        ]
        if _is_nanopore(row):
            args.extend(["--nanopore", "--ignore_indels", "--ignore_stop_codons"])
        return args, [
            (f"{sample_id}_resfinder.json", f"{sample_id}_resfinder.json", True),
            (meta, meta, True),
            ("pheno_table.txt", f"{sample_id}_pheno_table.txt", True),
            ("PointFinder_results.txt", f"{sample_id}_point_table.txt", False),
        ]

    def _write_resfinder_meta(self, path):
        """Database versions file in JASEN's format, read from each database's VERSION file."""
        records = []
        for name, db_dir in (("resfinder", self.options.db),
                             ("pointfinder", self.options.pointfinder_db)):
            try:
                with open(os.path.join(db_dir, "VERSION"), encoding="utf-8") as fin:
                    version = fin.read().replace("\r", "").replace("\n", "")
            except OSError:
                logger.warning("No VERSION file in %s; recording %s as unknown", db_dir, name)
                version = "unknown"
            records.append({"name": name, "version": version, "type": "database"})
        with open(path, "w", encoding="utf-8") as fout:
            json.dump(records, fout)

    def _shigatyper_args(self, row, work_dir):
        sample_id = row["sample_id"]
        if _is_nanopore(row):
            args = ["--SE", row["read1"], "--ont"]
        elif row.get("read2"):
            args = ["--R1", row["read1"], "--R2", row["read2"]]
        else:
            args = ["--SE", row["read1"]]
        args.extend(["--name", sample_id])
        return args, [
            (f"{sample_id}.tsv", f"{sample_id}.tsv", True),
            (f"{sample_id}-hits.tsv", f"{sample_id}-hits.tsv", False),
        ]
