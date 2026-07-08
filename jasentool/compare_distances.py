"""Compute pairwise cgMLST distance matrices for two chewBBACA outputs and their difference.

Each input is a chewBBACA allele-call table: one sample per row, the sample id in the
first column and the per-locus allele calls in the remaining columns. For each file a
sample x sample distance matrix is built where a cell is the number of loci at which the
two samples' calls differ (matching loci score 0, mismatching loci +1; missing/error
calls such as "-" are skipped). The per-file distance matrices and their element-wise
difference (matrix1 - matrix2) are written.

Because missing loci are skipped, a file with more missing data yields systematically
smaller distances. To attribute the difference to missing data the following are also
written: an absolute difference matrix (|distance1 - distance2|); a per-sample
missing-loci count summary (n_missing per file plus their delta) to spot version-wide
shifts in missing data; a dash_change matrix (per pair, loci comparable in exactly one of
the two files); and an unexplained matrix (max(0, |diff| - dash_change)) -- a lower bound
on the differences not attributable to missing data, i.e. genuine allele-call changes. The
dash_change and unexplained matrices require both files to list the same loci in the same
column order.

A call counts as missing unless it is an integer allele; chewBBACA inferred alleles
(`INF-<n>`) have the `INF-` prefix stripped and count as allele `<n>`. This rule is used by
the missing-loci summary, the ST plot, and dash_change, and matches cgmlst-dists, which
strips the alpha prefix so `INF-431` becomes allele 431 (only codes resolving to 0, e.g.
`-`/`LNF`/`NIPH`/`PLOT`/`ASM`, are missing). The in-Python fallback in
`jasentool.matrix.Matrix` does NOT strip `INF-`, so it differs there when cgmlst-dists is
absent.

Samples present in only one file are written to a separate missing-samples report and
excluded from the difference matrices, which run over the shared samples.

Per-file distances are computed with `cgmlst-dists` (each file is first written out
sorted by sample id with the `ST` column dropped); if the binary is unavailable the
in-Python `jasentool.matrix.Matrix` method is used instead. Diagnostic plots are also
written: a scatter and a Bland-Altman of the two files' pairwise distances, and -- when a
`sample_name,mlst_st` map is supplied -- per-sample missing-loci counts grouped by ST.
"""

import csv
import os
import subprocess
import sys
from io import StringIO

import matplotlib
matplotlib.use("Agg")  # headless: set before any pyplot import (incl. via jasentool.matrix)
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

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

    @classmethod
    def _build_dash_change_matrix(cls, calls1, calls2, sample_ids):
        """Per pair, count loci comparable in exactly one of the two files.

        A locus is "comparable" for a pair when neither sample is missing at it
        (missing per `_is_missing`: any non-integer call except stripped `INF-<n>`).
        This counts loci whose comparability flips between the two files (missing
        appeared or disappeared between versions), i.e. the loci through which
        differing missing data can change the distance. Symmetric and non-negative.

        Compares the two files locus-by-locus, so it assumes both list the same
        loci in the same column order.
        """
        n = len(sample_ids)
        mat = [[0] * n for _ in range(n)]
        for i in range(n):
            a1, a2 = calls1[sample_ids[i]], calls2[sample_ids[i]]
            for j in range(i + 1, n):
                b1, b2 = calls1[sample_ids[j]], calls2[sample_ids[j]]
                count = 0
                for x1, y1, x2, y2 in zip(a1, b1, a2, b2):
                    comparable1 = not cls._is_missing(x1) and not cls._is_missing(y1)
                    comparable2 = not cls._is_missing(x2) and not cls._is_missing(y2)
                    if comparable1 != comparable2:
                        count += 1
                mat[i][j] = count
                mat[j][i] = count
        return pd.DataFrame(mat, index=sample_ids, columns=sample_ids)

    @staticmethod
    def _is_missing(call):
        """True unless the call is a valid integer allele.

        chewBBACA inferred alleles are written `INF-<n>`; the `INF-` prefix is
        stripped so they count as the integer allele `<n>` (not missing). Every
        other non-integer value (`-`, `LNF`, `PLOT3`, `PLOT5`, `NIPH`, `ASM`, ...)
        is treated as missing.
        """
        value = call[4:] if call.startswith("INF-") else call
        return not value.isdigit()

    @classmethod
    def _n_missing(cls, alleles):
        """Count missing loci in a sample's allele list."""
        return sum(1 for call in alleles if cls._is_missing(call))

    @classmethod
    def _missing_per_sample_rows(cls, calls1, calls2):
        """Rows of (sample_id, n_missing_file1, n_missing_file2, delta) over all samples.

        delta = n_missing_file1 - n_missing_file2 when the sample is in both files,
        else blank. Counts are blank for files the sample is absent from.
        """
        all_ids = sorted(set(calls1) | set(calls2))
        rows = []
        for sid in all_ids:
            d1 = cls._n_missing(calls1[sid]) if sid in calls1 else None
            d2 = cls._n_missing(calls2[sid]) if sid in calls2 else None
            delta = d1 - d2 if d1 is not None and d2 is not None else ""
            rows.append((
                sid,
                "" if d1 is None else d1,
                "" if d2 is None else d2,
                delta,
            ))
        return rows

    @staticmethod
    def _write_clean_tsv(calls, path):
        """Write a sorted, ST-dropped TSV (FILE<tab>locus...) for cgmlst-dists."""
        sample_ids = sorted(calls)
        n_loci = len(calls[sample_ids[0]]) if sample_ids else 0
        with open(path, "w", newline="", encoding="utf-8") as fout:
            writer = csv.writer(fout, delimiter="\t")
            writer.writerow(["FILE"] + [f"locus_{i + 1}" for i in range(n_loci)])
            for sid in sample_ids:
                writer.writerow([sid] + calls[sid])

    # cgmlst-dists caps distances at its `-x` value (default 999), returning that
    # value early; raise it above the scheme's loci count so nothing is clamped.
    MAX_DISTANCE = 2000

    @classmethod
    def _distances_via_cgmlst_dists(cls, clean_path, bin_path):
        """Run cgmlst-dists on a cleaned TSV; return a DataFrame, or None on failure."""
        try:
            proc = subprocess.run(
                [bin_path, "-x", str(cls.MAX_DISTANCE), clean_path],
                capture_output=True, text=True, check=True,
            )
        except FileNotFoundError:
            logger.warning("cgmlst-dists binary '%s' not found; using Python fallback",
                           bin_path)
            return None
        except subprocess.CalledProcessError as exc:
            logger.warning("cgmlst-dists failed (exit %s); using Python fallback: %s",
                           exc.returncode, (exc.stderr or "").strip())
            return None
        matrix = pd.read_csv(StringIO(proc.stdout), sep="\t", index_col=0)
        matrix.index = matrix.index.astype(str)
        matrix.columns = matrix.columns.astype(str)
        matrix.index.name = None
        return matrix

    def _distance_matrix(self, calls, stem):
        """Per-file distance matrix via cgmlst-dists, falling back to the Python method."""
        clean_path = os.path.join(self.options.output_dir, f"{stem}_clean.tsv")
        self._write_clean_tsv(calls, clean_path)
        logger.info("Wrote %s", clean_path)
        matrix = self._distances_via_cgmlst_dists(clean_path, self.options.cgmlst_dists_bin)
        if matrix is None:
            matrix = Matrix.generate_matrix(list(calls), lambda sid: calls[sid])
        else:
            logger.info("Computed %s distances with cgmlst-dists", stem)
        return matrix

    @staticmethod
    def _read_st_map(path):
        """Read a sample_name,mlst_st table into {sample_id: st}; skips a header row."""
        delimiter = CompareDistances._detect_delimiter(path)
        with open(path, newline="", encoding="utf-8") as fin:
            rows = [r for r in csv.reader(fin, delimiter=delimiter) if r and len(r) >= 2]
        header_terms = {"sample_name", "sample", "sample_id", "mlst_st", "st", "mlst"}
        if rows and any(cell.strip().lower() in header_terms for cell in rows[0]):
            rows = rows[1:]
        return {r[0].strip(): r[1].strip() for r in rows}

    @staticmethod
    def _st_order(values):
        """Order ST labels numerically when possible, else lexicographically."""
        return sorted(set(values), key=lambda s: (0, int(s)) if str(s).isdigit() else (1, str(s)))

    def _distance_plots(self, matrix1, matrix2, shared, stem1, stem2):
        """Scatter and Bland-Altman of the two files' pairwise distances (upper triangle)."""
        if len(shared) < 2:
            logger.warning("Fewer than 2 shared samples; skipping distance plots")
            return
        m1 = matrix1.loc[shared, shared].to_numpy(dtype=float)
        m2 = matrix2.loc[shared, shared].to_numpy(dtype=float)
        iu = np.triu_indices(len(shared), k=1)
        d1, d2 = m1[iu], m2[iu]

        if getattr(self.options, "verbose", False):
            points = pd.DataFrame({
                "sample_a": [shared[a] for a in iu[0]],
                "sample_b": [shared[b] for b in iu[1]],
                f"{stem1}_distance": d1.astype(int),
                f"{stem2}_distance": d2.astype(int),
                "mean": (d1 + d2) / 2,
                "diff": (d1 - d2).astype(int),
            })
            pts_path = os.path.join(
                self.options.output_dir, f"{stem1}_vs_{stem2}_distance_points.tsv")
            points.to_csv(pts_path, sep="\t", index=False)
            logger.info("Wrote %s (%d pairs; feeds both the scatter and Bland-Altman)",
                        pts_path, len(points))

        plt.figure(figsize=(8, 8))
        plt.scatter(d1, d2, s=8, alpha=0.3)
        lim = max(d1.max(), d2.max(), 1)
        plt.plot([0, lim], [0, lim], color="red", lw=1)
        plt.xlabel(f"{stem1} distance")
        plt.ylabel(f"{stem2} distance")
        plt.title("Pairwise cgMLST distances")
        scatter_path = os.path.join(
            self.options.output_dir, f"{stem1}_vs_{stem2}_distance_scatter.png")
        plt.tight_layout()
        plt.savefig(scatter_path, dpi=300)
        plt.close()
        logger.info("Wrote %s", scatter_path)

        mean, diff = (d1 + d2) / 2, d1 - d2
        md, sd = diff.mean(), diff.std()
        ba_path = os.path.join(
            self.options.output_dir, f"{stem1}_vs_{stem2}_bland_altman.png")
        self._bland_altman(mean, diff, md, sd, stem1, stem2, ba_path)
        logger.info("Wrote %s", ba_path)

        # Optional zoomed Bland-Altman restricted to a clinically relevant
        # mean-distance window, written alongside the full-range plot. The
        # reference lines (bias, ±1.96 SD) stay computed over all pairs so the
        # zoom is a pure view onto the same statistics.
        lo = getattr(self.options, "min_mean_distance", None)
        hi = getattr(self.options, "max_mean_distance", None)
        if lo is not None or hi is not None:
            lo_eff = float(lo) if lo is not None else 0.0
            hi_eff = float(hi) if hi is not None else float(mean.max())
            zoom_path = os.path.join(
                self.options.output_dir,
                f"{stem1}_vs_{stem2}_bland_altman_mean_{lo_eff:g}-{hi_eff:g}.png")
            self._bland_altman(mean, diff, md, sd, stem1, stem2, zoom_path,
                               xlim=(lo_eff, hi_eff))
            logger.info("Wrote %s", zoom_path)

    def _bland_altman(self, mean, diff, md, sd, stem1, stem2, path, xlim=None):
        """Draw a Bland-Altman plot; xlim optionally restricts the mean-distance axis."""
        loa_hi, loa_lo = md + 1.96 * sd, md - 1.96 * sd
        plt.figure(figsize=(8, 6))
        plt.scatter(mean, diff, s=8, alpha=0.3)
        plt.axhline(md, color="red", lw=1, label=f"mean {md:.2f}")
        plt.axhline(loa_hi, color="grey", ls="--", lw=1, label="±1.96 SD")
        plt.axhline(loa_lo, color="grey", ls="--", lw=1)
        plt.xlabel("Mean distance")
        plt.ylabel(f"Difference ({stem1} - {stem2})")
        title = "Bland-Altman of pairwise distances"
        if xlim is not None:
            lo, hi = xlim
            plt.xlim(lo, hi)
            title += f" (mean {lo:g}-{hi:g})"
            # Rescale y to the points inside the window plus the agreement lines,
            # so the zoom isn't vertically squished by out-of-window outliers.
            in_win = (mean >= lo) & (mean <= hi)
            ys = np.concatenate([diff[in_win], [md, loa_hi, loa_lo]])
            if ys.size:
                pad = max((float(ys.max()) - float(ys.min())) * 0.05, 1.0)
                plt.ylim(float(ys.min()) - pad, float(ys.max()) + pad)
        plt.title(title)
        plt.legend()
        plt.tight_layout()
        plt.savefig(path, dpi=300)
        plt.close()

    def _missing_vs_st_plot(self, calls1, calls2, stem1, stem2):
        """Per-sample missing-loci ('-') counts grouped by MLST ST, for both files."""
        st_map = self._read_st_map(self.options.mlst)
        records = []
        for stem, calls in ((stem1, calls1), (stem2, calls2)):
            for sid, alleles in calls.items():
                if sid in st_map:
                    records.append({"sample": sid, "ST": st_map[sid], "version": stem,
                                    "n_missing": self._n_missing(alleles)})
        unmatched = (set(calls1) | set(calls2)) - set(st_map)
        if unmatched:
            logger.warning("%d sample(s) not in the MLST map (excluded from ST plot): %s",
                           len(unmatched), ", ".join(sorted(unmatched)))
        if not records:
            logger.warning("No samples matched the MLST map; skipping missing-vs-ST plot")
            return
        df = pd.DataFrame(records)
        if getattr(self.options, "verbose", False):
            pts_path = os.path.join(
                self.options.output_dir, f"{stem1}_vs_{stem2}_missing_vs_st_points.tsv")
            df.sort_values(["ST", "version", "sample"]).to_csv(pts_path, sep="\t", index=False)
            logger.info("Wrote %s", pts_path)

        order = self._st_order(df["ST"])
        plt.figure(figsize=(max(8, 0.6 * len(order)), 6))
        sns.boxplot(data=df, x="ST", y="n_missing", hue="version", order=order)
        sns.stripplot(data=df, x="ST", y="n_missing", hue="version", order=order,
                      dodge=True, size=3, alpha=0.5, legend=False)
        plt.xticks(rotation=90)
        plt.xlabel("MLST ST")
        plt.ylabel("Missing loci per sample")
        plt.title("Missing loci vs MLST ST")
        path = os.path.join(
            self.options.output_dir, f"{stem1}_vs_{stem2}_missing_vs_st.png")
        plt.tight_layout()
        plt.savefig(path, dpi=300)
        plt.close()
        logger.info("Wrote %s", path)

    def run(self):
        """Read both tables, build their distance matrices, write the matrices and diff."""
        for fpath in (self.options.file1, self.options.file2):
            if not os.path.isfile(fpath):
                logger.error("Input not a file: %s", fpath)
                sys.exit(1)

        calls1 = self._read_calls(self.options.file1)
        calls2 = self._read_calls(self.options.file2)

        file1_name = os.path.basename(self.options.file1)
        file2_name = os.path.basename(self.options.file2)
        os.makedirs(self.options.output_dir, exist_ok=True)
        stem1 = os.path.splitext(file1_name)[0]
        stem2 = os.path.splitext(file2_name)[0]
        if stem1 == stem2:
            stem1, stem2 = f"{stem1}_1", f"{stem2}_2"

        matrix1 = self._distance_matrix(calls1, stem1)
        matrix2 = self._distance_matrix(calls2, stem2)

        # Identify samples present in one file but not the other. These are
        # excluded from the difference matrix, which still runs on shared samples.
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
        abs_diff = diff.abs()

        # Missing-data control: dash_change counts loci whose comparability flips
        # between the files (needs equal loci counts / same column order). The
        # unexplained residual is the part of |diff| not coverable by those flips
        # (a lower bound on genuine allele-call differences).
        loci1 = len(next(iter(calls1.values())))
        loci2 = len(next(iter(calls2.values())))
        dash_change = unexplained = None
        if loci1 == loci2:
            dash_change = self._build_dash_change_matrix(calls1, calls2, shared)
            unexplained = (abs_diff - dash_change).clip(lower=0)
        else:
            logger.warning(
                "Loci counts differ (%d vs %d); skipping dash_change/unexplained "
                "matrices (they require matching loci/column order)", loci1, loci2)

        # Sort rows and columns by sample id so all matrices share a stable,
        # readable ordering regardless of input row order.
        def _sorted(frame):
            return frame.sort_index(axis=0).sort_index(axis=1)

        outputs = [
            (matrix1, f"{stem1}_distance_matrix.tsv"),
            (matrix2, f"{stem2}_distance_matrix.tsv"),
            (diff, f"{stem1}_vs_{stem2}_diff_matrix.tsv"),
            (abs_diff, f"{stem1}_vs_{stem2}_abs_diff_matrix.tsv"),
        ]
        if dash_change is not None:
            outputs.append((dash_change, f"{stem1}_vs_{stem2}_dash_change_matrix.tsv"))
            outputs.append((unexplained, f"{stem1}_vs_{stem2}_unexplained_matrix.tsv"))
        for frame, name in outputs:
            fpath = os.path.join(self.options.output_dir, name)
            _sorted(frame).to_csv(fpath, sep="\t")
            logger.info("Wrote %s", fpath)

        # Per-sample missing-loci counts in each file, to spot version changes in
        # missing data (missing = any non-integer call except stripped INF-<n>).
        out_per_sample = os.path.join(
            self.options.output_dir, f"{stem1}_vs_{stem2}_missing_loci_per_sample.tsv")
        with open(out_per_sample, "w", newline="", encoding="utf-8") as fout:
            writer = csv.writer(fout, delimiter="\t")
            writer.writerow(["sample_id", f"n_missing_{stem1}", f"n_missing_{stem2}", "delta"])
            writer.writerows(self._missing_per_sample_rows(calls1, calls2))
        logger.info("Wrote %s", out_per_sample)

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

        # Diagnostic plots.
        self._distance_plots(matrix1, matrix2, shared, stem1, stem2)
        if getattr(self.options, "mlst", None):
            self._missing_vs_st_plot(calls1, calls2, stem1, stem2)
