"""Compute pairwise cgMLST distance matrices for two chewBBACA outputs and their difference.

Each input is a chewBBACA allele-call table: one sample per row, the sample id in the
first column and the per-locus allele calls in the remaining columns. For each file a
sample x sample distance matrix is built where a cell is the number of loci at which the
two samples' calls differ (matching loci score 0, mismatching loci +1; missing/error
calls such as "-" are skipped). Three matrices are written: one per input file and their
element-wise difference (matrix1 - matrix2).

The pairwise comparison and matrix subtraction reuse `jasentool.matrix.Matrix`.
"""

import csv
import os
import sys

from jasentool.matrix import Matrix
from jasentool.log import get_logger

logger = get_logger(__name__)


class CompareDistances:
    """Build and diff cgMLST distance matrices from two chewBBACA allele-call tables."""

    def __init__(self, options):
        self.options = options

    @staticmethod
    def _detect_delimiter(fpath):
        """chewBBACA tables are tab-separated; fall back to comma if no tab is present."""
        with open(fpath, encoding="utf-8") as fin:
            first_line = fin.readline()
        return "\t" if "\t" in first_line else ","

    def _read_calls(self, fpath):
        """Return an ordered {sample_id: [allele_calls]} dict from a chewBBACA table."""
        delimiter = self._detect_delimiter(fpath)
        with open(fpath, newline="", encoding="utf-8") as fin:
            rows = [row for row in csv.reader(fin, delimiter=delimiter) if row]
        if not rows:
            logger.error("No rows in %s", fpath)
            sys.exit(1)

        # chewBBACA results tables lead with a "FILE" header row; drop it if present.
        if rows[0][0].strip().upper() == "FILE":
            rows = rows[1:]

        calls = {}
        n_loci = None
        for row in rows:
            sample_id = row[0].strip()
            allele_calls = [call.strip() for call in row[1:]]
            if n_loci is None:
                n_loci = len(allele_calls)
            elif len(allele_calls) != n_loci:
                logger.error("Sample %s in %s has %d loci, expected %d",
                             sample_id, fpath, len(allele_calls), n_loci)
                sys.exit(1)
            if sample_id in calls:
                logger.error("Duplicate sample id %s in %s", sample_id, fpath)
                sys.exit(1)
            calls[sample_id] = allele_calls

        if not calls:
            logger.error("No samples in %s", fpath)
            sys.exit(1)
        logger.info("Read %d samples (%d loci) from %s", len(calls), n_loci, fpath)
        return calls

    def run(self):
        """Read both tables, build their distance matrices, write the matrices and diff."""
        for fpath in (self.options.file1, self.options.file2):
            if not os.path.isfile(fpath):
                logger.error("Input not a file: %s", fpath)
                sys.exit(1)

        calls1 = self._read_calls(self.options.file1)
        calls2 = self._read_calls(self.options.file2)

        matrix1 = Matrix.generate_matrix(list(calls1), lambda sid: calls1[sid])
        matrix2 = Matrix.generate_matrix(list(calls2), lambda sid: calls2[sid])

        # Difference matrix over the samples shared by both files.
        shared = [sid for sid in calls1 if sid in calls2]
        only_in_1 = [sid for sid in calls1 if sid not in calls2]
        only_in_2 = [sid for sid in calls2 if sid not in calls1]
        if only_in_1:
            logger.warning("Samples only in %s: %s", self.options.file1, ", ".join(only_in_1))
        if only_in_2:
            logger.warning("Samples only in %s: %s", self.options.file2, ", ".join(only_in_2))
        if not shared:
            logger.error("No shared samples between the two files")
            sys.exit(1)
        diff = (matrix1.loc[shared, shared].astype(float)
                - matrix2.loc[shared, shared].astype(float))

        os.makedirs(self.options.output_dir, exist_ok=True)
        stem1 = os.path.splitext(os.path.basename(self.options.file1))[0]
        stem2 = os.path.splitext(os.path.basename(self.options.file2))[0]
        if stem1 == stem2:
            stem1, stem2 = f"{stem1}_1", f"{stem2}_2"
        out1 = os.path.join(self.options.output_dir, f"{stem1}_distance_matrix.tsv")
        out2 = os.path.join(self.options.output_dir, f"{stem2}_distance_matrix.tsv")
        out_diff = os.path.join(self.options.output_dir, f"{stem1}_vs_{stem2}_diff_matrix.tsv")
        matrix1.to_csv(out1, sep="\t")
        matrix2.to_csv(out2, sep="\t")
        diff.to_csv(out_diff, sep="\t")
        logger.info("Wrote %s", out1)
        logger.info("Wrote %s", out2)
        logger.info("Wrote %s", out_diff)
