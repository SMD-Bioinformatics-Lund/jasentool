"""Re-run chewBBACA AlleleCall on backed-up masked assemblies.

Consumes `<stem>_masked_assemblies.csv` produced by `jasentool check-backup`,
writes a batch-input file with one masked FASTA path per line, then runs
`chewie AlleleCall` once across the whole batch. Mirrors how JASEN itself
feeds chewBBACA at `subworkflows/typing.nf:125-131`.
"""

import csv
import os
import subprocess
import sys

from jasentool.log import get_logger

logger = get_logger(__name__)


class RerunChewbbaca:
    """Batch-run chewBBACA AlleleCall from a check-backup masked-assemblies CSV."""

    def __init__(self, options):
        self.options = options

    def run(self):
        """Validate inputs, write the batch list, exec chewie AlleleCall."""
        if not os.path.isfile(self.options.masked_assemblies):
            logger.error("--masked-assemblies not a file: %s", self.options.masked_assemblies)
            sys.exit(1)
        if not os.path.isdir(self.options.schema_dir):
            logger.error("--schema-dir not a directory: %s", self.options.schema_dir)
            sys.exit(1)
        if self.options.training_file and not os.path.isfile(self.options.training_file):
            logger.error("--training-file not a file: %s", self.options.training_file)
            sys.exit(1)
        if self.options.singularity_image and not os.path.isfile(self.options.singularity_image):
            logger.error("--singularity-image not a file: %s", self.options.singularity_image)
            sys.exit(1)

        paths = self._collect_paths()
        if not paths:
            logger.error("No masked assemblies to process")
            sys.exit(1)

        os.makedirs(self.options.output_dir, exist_ok=True)
        batch_list = os.path.join(self.options.output_dir, "batch_input.list")
        chewie_out = os.path.join(self.options.output_dir, "output_dir")
        with open(batch_list, "w", encoding="utf-8") as fout:
            for path in paths:
                fout.write(f"{path}\n")
        logger.info("Wrote %d paths to %s", len(paths), batch_list)

        cmd = []
        if self.options.singularity_image:
            cmd.extend(["singularity", "exec"])
            if self.options.singularity_bind:
                cmd.extend(["--bind", self.options.singularity_bind])
            cmd.append(self.options.singularity_image)
        cmd.extend([
            self.options.chewie_bin, "AlleleCall",
            "-i", batch_list,
            "--cpu", str(self.options.cpus),
            "--output-directory", chewie_out,
            "--schema-directory", self.options.schema_dir,
        ])
        if self.options.training_file:
            cmd.extend(["--ptf", self.options.training_file])

        logger.info("Running: %s", " ".join(cmd))
        completed = subprocess.run(cmd, check=False)
        sys.exit(completed.returncode)

    def _collect_paths(self):
        """Read masked-assembly paths from the CSV, filter by profile, drop missing files."""
        paths = []
        skipped_profile = 0
        skipped_missing = 0
        with open(self.options.masked_assemblies, "r", newline="", encoding="utf-8") as fin:
            reader = csv.DictReader(fin)
            for row in reader:
                if self.options.profile_filter and row.get("profile") != self.options.profile_filter:
                    skipped_profile += 1
                    continue
                path = row.get("masked_assembly_path")
                if not path:
                    continue
                if not os.path.isfile(path):
                    logger.warning("Missing file for %s: %s", row.get("sample_id"), path)
                    skipped_missing += 1
                    continue
                paths.append(path)
        # de-duplicate while preserving order
        seen = set()
        deduped = []
        for path in paths:
            if path not in seen:
                seen.add(path)
                deduped.append(path)
        if skipped_profile:
            logger.info("Skipped %d rows by --profile-filter", skipped_profile)
        if skipped_missing:
            logger.info("Skipped %d rows whose file was missing", skipped_missing)
        return deduped
