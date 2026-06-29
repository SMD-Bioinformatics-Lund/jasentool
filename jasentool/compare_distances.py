"""Compute pairwise cgMLST distance matrices for two chewBBACA outputs and their difference.

Each input is a chewBBACA allele-call table: one sample per row, the sample id in the
first column and the per-locus allele calls in the remaining columns. For each file a
sample x sample distance matrix is built where a cell is the number of loci at which the
two samples' calls differ (matching loci score 0, mismatching loci +1; missing/error
calls such as "-" are skipped). The per-file distance matrices and their element-wise
difference (matrix1 - matrix2) are written.

Because "-" loci are skipped, a file with more missing data yields systematically smaller
distances. To control for this, a signed "-" matrix is also built per file: per pair it
counts loci where only the row sample is "-" (+1) minus loci where only the column sample
is "-" (-1), with both-"-" and neither-"-" loci scoring 0 (so the matrix is
skew-symmetric). Their difference (dash1 - dash2) is subtracted from the distance
difference to give a corrected difference matrix.

Samples present in only one file are written to a separate missing-samples report and
excluded from the difference matrices, which run over the shared samples.

The pairwise comparison and matrix subtraction reuse `jasentool.matrix.Matrix`.
"""

import csv
import os
import sys

import pandas as pd

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

    # First-column header markers across chewBBACA versions: newer outputs lead
    # with "FILE", older ones with "#Name".
    HEADER_MARKERS = {"FILE", "#NAME", "NAME"}

    def _read_calls(self, fpath):
        """Return an ordered {sample_id: [allele_calls]} dict from a chewBBACA table.

        A header row is required (errors otherwise) and may use either style:
        newer `FILE<tab>locus...` or older `#Name<tab>ST<tab>locus...`. The sample
        id comes from the first column and an `ST` column (older AlleleCall output)
        is dropped so only per-locus calls remain.
        """
        delimiter = self._detect_delimiter(fpath)
        with open(fpath, newline="", encoding="utf-8") as fin:
            rows = [row for row in csv.reader(fin, delimiter=delimiter) if row]
        if not rows:
            logger.error("No rows in %s", fpath)
            sys.exit(1)

        # A header row is required; the first column is the sample name.
        first_cell = rows[0][0].strip()
        if not (first_cell.upper() in self.HEADER_MARKERS or first_cell.startswith("#")):
            logger.error(
                "Expected a header row (first column 'FILE' or '#Name') in %s, got %r",
                fpath, first_cell,
            )
            sys.exit(1)

        header = rows[0]
        rows = rows[1:]
        # Column indices to ignore when collecting per-locus calls: the sample id
        # (col 0) and an "ST" column if the older output includes one.
        st_index = next(
            (i for i, col in enumerate(header) if col.strip().upper() == "ST"),
            None,
        )
        if st_index is not None:
            logger.info("Dropping 'ST' column (index %d) from %s", st_index, fpath)

        drop = {0} if st_index is None else {0, st_index}

        calls = {}
        n_loci = None
        for row in rows:
            sample_id = row[0].strip()
            allele_calls = [call.strip() for i, call in enumerate(row) if i not in drop]
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

    @staticmethod
    def _build_dash_matrix(calls):
        """Pairwise signed count of loci where exactly one of the pair is "-".

        Per locus: only the row sample is "-" -> +1; only the column sample is
        "-" -> -1; both "-" or neither "-" -> 0. The matrix is therefore
        skew-symmetric (cell[i][j] == -cell[j][i]) and measures the imbalance in
        missing data between the two samples.
        """
        sample_ids = list(calls)
        n = len(sample_ids)
        mat = [[0] * n for _ in range(n)]
        for i in range(n):
            row_calls = calls[sample_ids[i]]
            for j in range(i + 1, n):
                col_calls = calls[sample_ids[j]]
                count = sum(
                    (1 if x == "-" and y != "-" else 0)
                    - (1 if y == "-" and x != "-" else 0)
                    for x, y in zip(row_calls, col_calls)
                )
                mat[i][j] = count
                mat[j][i] = -count
        return pd.DataFrame(mat, index=sample_ids, columns=sample_ids)

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

        # "-" (missing) control: per-pair count of loci skipped due to a "-" call.
        dash1 = self._build_dash_matrix(calls1)
        dash2 = self._build_dash_matrix(calls2)

        # Identify samples present in one file but not the other. These are
        # excluded from the difference matrix, which still runs on shared samples.
        file1_name = os.path.basename(self.options.file1)
        file2_name = os.path.basename(self.options.file2)
        shared = [sid for sid in calls1 if sid in calls2]
        only_in_1 = [sid for sid in calls1 if sid not in calls2]
        only_in_2 = [sid for sid in calls2 if sid not in calls1]
        if only_in_1:
            logger.warning("Samples in %s missing from %s: %s",
                           file1_name, file2_name, ", ".join(only_in_1))
        if only_in_2:
            logger.warning("Samples in %s missing from %s: %s",
                           file2_name, file1_name, ", ".join(only_in_2))
        if not shared:
            logger.error("No shared samples between the two files")
            sys.exit(1)
        diff = (matrix1.loc[shared, shared].astype(float)
                - matrix2.loc[shared, shared].astype(float))
        dash_diff = (dash1.loc[shared, shared].astype(float)
                     - dash2.loc[shared, shared].astype(float))
        # Subtract the "-" differential to control for differing amounts of missing
        # data between the two files skewing the raw distance difference.
        corrected_diff = diff - dash_diff

        # Sort rows and columns by sample id so all matrices share a stable,
        # readable ordering regardless of input row order.
        def _sorted(frame):
            return frame.sort_index(axis=0).sort_index(axis=1)

        matrix1, matrix2, diff = _sorted(matrix1), _sorted(matrix2), _sorted(diff)
        dash1, dash2, dash_diff = _sorted(dash1), _sorted(dash2), _sorted(dash_diff)
        corrected_diff = _sorted(corrected_diff)

        os.makedirs(self.options.output_dir, exist_ok=True)
        stem1 = os.path.splitext(file1_name)[0]
        stem2 = os.path.splitext(file2_name)[0]
        if stem1 == stem2:
            stem1, stem2 = f"{stem1}_1", f"{stem2}_2"
        outputs = [
            (matrix1, f"{stem1}_distance_matrix.tsv"),
            (matrix2, f"{stem2}_distance_matrix.tsv"),
            (diff, f"{stem1}_vs_{stem2}_diff_matrix.tsv"),
            (dash1, f"{stem1}_dash_matrix.tsv"),
            (dash2, f"{stem2}_dash_matrix.tsv"),
            (dash_diff, f"{stem1}_vs_{stem2}_dash_diff_matrix.tsv"),
            (corrected_diff, f"{stem1}_vs_{stem2}_corrected_diff_matrix.tsv"),
        ]
        for frame, name in outputs:
            fpath = os.path.join(self.options.output_dir, name)
            frame.to_csv(fpath, sep="\t")
            logger.info("Wrote %s", fpath)

        # Report of samples excluded from the diff because they're missing from
        # one file. Always written (header-only when both files share all samples).
        out_missing = os.path.join(
            self.options.output_dir, f"{stem1}_vs_{stem2}_missing_samples.tsv")
        with open(out_missing, "w", newline="", encoding="utf-8") as fout:
            writer = csv.writer(fout, delimiter="\t")
            writer.writerow(["sample_id", "present_in", "missing_from"])
            writer.writerows((sid, file1_name, file2_name) for sid in only_in_1)
            writer.writerows((sid, file2_name, file1_name) for sid in only_in_2)
        logger.info("Wrote %s (%d sample(s) missing from one file)",
                    out_missing, len(only_in_1) + len(only_in_2))
