"""Cross-check Bonsai samples against the backup storage tree."""

import csv
import fnmatch
import os
from collections import Counter

from tqdm import tqdm

from jasentool.config import get_profile
from jasentool.database import Database
from jasentool.log import get_logger

logger = get_logger(__name__)

ASSEMBLERS = ("spades", "skesa", "flye", "medaka")


class CheckBackup:
    """Compare Bonsai sample documents against on-disk backup outputs."""

    def __init__(self, options):
        self.options = options
        self.profile = options.profile
        self.backup_dir = options.backup_dir
        self.output_file = options.output_file

    @staticmethod
    def fetch_samples(db_collection, profile):
        """Pull Bonsai samples whose `pipeline.analysis_profile` contains `profile`.

        Mongo array-equality semantics: querying `{"pipeline.analysis_profile": X}`
        matches any document whose `analysis_profile` list contains X.
        """
        query = {"pipeline.analysis_profile": profile}
        projection = {
            "_id": 0,
            "sample_id": 1,
            "sample_name": 1,
            "lims_id": 1,
            "pipeline.analysis_profile": 1,
            "species_prediction.scientific_name": 1,
        }
        return Database.find(db_collection, query, projection)

    def scan(self, samples, outputs, species, species_full=None):
        """Walk each sample x expected output, return (summary_rows, missing_rows)."""
        summary_rows = []
        missing_rows = []
        progress = tqdm(
            samples,
            total=len(samples),
            desc=f"check-backup [{self.profile}]",
            unit="sample",
        )
        # TODO performance: pre-list every distinct (species, dirname) into a set
        # so wildcard-mask entries don't trigger one os.listdir per sample on NFS.
        for doc in progress:
            sample_id = doc.get("sample_id")
            if not sample_id:
                logger.warning("Skipping bonsai doc with no sample_id: %s", doc)
                continue
            _check_species_sanity(doc, species_full)
            row, doc_missing = self._scan_sample(doc, outputs, species)
            row["missing_software_output"] = ";".join(
                m["software_name"] for m in doc_missing
            )
            summary_rows.append(row)
            missing_rows.extend(doc_missing)
        return summary_rows, missing_rows

    def _scan_sample(self, doc, outputs, species):
        """Scan one bonsai doc; return (summary_row, list_of_missing_rows)."""
        sample_id = doc["sample_id"]
        sample_name = doc.get("sample_name", "")
        lims_id = doc.get("lims_id", "")
        counters = {"req_total": 0, "req_found": 0, "opt_total": 0, "opt_found": 0}
        doc_missing = []
        for output in outputs:
            self._check_one_output(sample_id, output, species, counters, doc_missing,
                                   sample_name=sample_name, lims_id=lims_id)
        status = (
            "PASS"
            if counters["req_total"] and counters["req_found"] == counters["req_total"]
            else "FAIL"
        )
        summary_row = {
            "sample_id": sample_id,
            "sample_name": sample_name,
            "lims_id": lims_id,
            "profile": self.profile,
            "required_expected": counters["req_total"],
            "required_found": counters["req_found"],
            "optional_expected": counters["opt_total"],
            "optional_found": counters["opt_found"],
            "status": status,
        }
        return summary_row, doc_missing

    def _check_one_output(self, sample_id, output, species, counters, doc_missing,
                          sample_name="", lims_id=""):
        """Update `counters` and append to `doc_missing` for a single expected output."""
        required = output.get("required", True)
        if required:
            counters["req_total"] += 1
        else:
            counters["opt_total"] += 1
        dirname = output["dirname"]
        mask = output.get("mask", "")
        exts = _as_list(output["file_ext"])
        search_dir = os.path.join(self.backup_dir, species, dirname)
        found_any = any(
            _glob_matches(search_dir, sample_id, mask, ext) for ext in exts
        )
        if found_any:
            if required:
                counters["req_found"] += 1
            else:
                counters["opt_found"] += 1
            return
        doc_missing.append({
            "sample_id": sample_id,
            "sample_name": sample_name,
            "lims_id": lims_id,
            "profile": self.profile,
            "software_name": output["software_name"],
            "software_dirname": dirname,
            "expected_glob": _format_glob(sample_id, mask, exts),
            "searched_path": search_dir,
            "required": str(required),
        })

    def find_orphans(self, sample_ids, outputs, species):
        """Walk declared (species, dirname) dirs; return files not matching any expected output.

        Wildcard-mask outputs are skipped (their dir contents can't be bounded
        without per-file fnmatch on every sample). Currently no active outputs
        use wildcards, but the guard keeps future config edits safe.
        """
        expected_per_dir = {}
        skipped_dirs = set()
        for output in outputs:
            dirname = output["dirname"]
            mask = output.get("mask", "")
            if "*" in mask:
                logger.warning(
                    "Orphan check skips wildcard mask for %s", output["software_name"],
                )
                skipped_dirs.add(dirname)
                continue
            exts = _as_list(output["file_ext"])
            bucket = expected_per_dir.setdefault(dirname, set())
            for sid in sample_ids:
                for ext in exts:
                    bucket.add(f"{sid}{mask}{ext}")

        sample_ids_desc = sorted(sample_ids, key=len, reverse=True)
        orphans = []
        for dirname, expected in expected_per_dir.items():
            if dirname in skipped_dirs:
                continue
            search_dir = os.path.join(self.backup_dir, species, dirname)
            if not os.path.isdir(search_dir):
                continue
            for name in os.listdir(search_dir):
                if name in expected:
                    continue
                if (name.endswith("_versions.yml")
                        and _versions_sample_id(name, sample_ids_desc) is not None):
                    continue
                orphans.append({
                    "filepath": os.path.join(search_dir, name),
                    "species": species,
                    "software_dirname": dirname,
                    "filename": name,
                })
        return orphans

    def run(self):
        """Entry point: resolve profile, fetch samples, scan disk, write outputs."""
        profile_entry = get_profile(self.profile)
        species = profile_entry["species"]
        species_full = profile_entry.get("species_full")
        outputs = profile_entry.get("outputs", []) or []
        if not outputs:
            logger.warning(
                "Profile '%s' has no outputs declared in jasentool.config; every "
                "sample will FAIL.", self.profile,
            )

        Database.initialize(self.options.db_name, uri=self.options.address)
        samples = self.fetch_samples(self.options.db_collection, self.profile)
        logger.info(
            "%d bonsai samples for profile=%s (from %s/%s)",
            len(samples), self.profile, self.options.db_name, self.options.db_collection,
        )

        summary_rows, missing_rows = self.scan(samples, outputs, species, species_full)

        _write_csv(self.output_file, summary_rows, fieldnames=[
            "sample_id", "sample_name", "lims_id", "profile",
            "required_expected", "required_found",
            "optional_expected", "optional_found",
            "missing_software_output", "status",
        ])
        missing_fpath = os.path.splitext(self.output_file)[0] + "_missing.csv"
        _write_csv(missing_fpath, missing_rows, fieldnames=[
            "sample_id", "sample_name", "lims_id", "profile",
            "software_name", "software_dirname",
            "expected_glob", "searched_path", "required",
        ])

        stats_rows = _per_output_stats(outputs, missing_rows, total=len(summary_rows))
        stats_fpath = os.path.splitext(self.output_file)[0] + "_stats.csv"
        _write_csv(stats_fpath, stats_rows, fieldnames=[
            "software_name", "dirname", "mask", "file_ext", "required",
            "n_missing", "n_found", "total_samples", "missing_pct",
        ])

        review_rows = _detect_sample_quirks(samples, self.profile)
        review_fpath = os.path.splitext(self.output_file)[0] + "_review.csv"
        _write_csv(review_fpath, review_rows, fieldnames=[
            "sample_id", "sample_name", "lims_id", "profile", "reason",
        ])
        logger.info("%d sample-review rows written (see %s)",
                    len(review_rows), review_fpath)

        assembly_rows = _collect_assembly_paths(
            samples, self.backup_dir, species, self.profile,
        )
        assembly_fpath = os.path.splitext(self.output_file)[0] + "_assemblies.csv"
        _write_csv(assembly_fpath, assembly_rows, fieldnames=[
            "sample_id", "sample_name", "lims_id", "profile",
            "assembler", "assembly_path",
        ])
        logger.info("%d backed-up assembly FASTAs listed (see %s)",
                    len(assembly_rows), assembly_fpath)

        passed = sum(1 for r in summary_rows if r["status"] == "PASS")
        failed = len(summary_rows) - passed
        logger.info("%d samples expected; %d backed up; %d not yet backed up",
                    len(summary_rows), passed, failed)
        _log_top_missing(stats_rows)

        if getattr(self.options, "check_orphans", False):
            sample_ids = [r["sample_id"] for r in summary_rows]
            orphans = self.find_orphans(sample_ids, outputs, species)
            orphan_fpath = os.path.splitext(self.output_file)[0] + "_orphans.csv"
            _write_csv(orphan_fpath, orphans, fieldnames=[
                "filepath", "species", "software_dirname", "filename",
            ])
            logger.info("%d orphan files in backup tree (see %s)",
                        len(orphans), orphan_fpath)


def _per_output_stats(outputs, missing_rows, total):
    """Return one row per declared output with miss/found counts and percentage.

    Sorted by `n_missing` descending so the worst offenders are at the top.
    """
    miss_counts = {}
    for row in missing_rows:
        sw = row["software_name"]
        miss_counts[sw] = miss_counts.get(sw, 0) + 1
    rows = []
    for output in outputs:
        sw = output["software_name"]
        n_missing = miss_counts.get(sw, 0)
        pct = (n_missing / total * 100) if total else 0.0
        ext_value = output["file_ext"]
        ext_display = "|".join(_as_list(ext_value))
        rows.append({
            "software_name": sw,
            "dirname": output["dirname"],
            "mask": output.get("mask", ""),
            "file_ext": ext_display,
            "required": str(output.get("required", True)),
            "n_missing": n_missing,
            "n_found": total - n_missing,
            "total_samples": total,
            "missing_pct": f"{pct:.1f}",
        })
    rows.sort(key=lambda r: r["n_missing"], reverse=True)
    return rows


def _log_top_missing(stats_rows, top_n=10):
    """Log the worst-offending outputs so the user sees them without opening the CSV."""
    offenders = [r for r in stats_rows if r["n_missing"] > 0][:top_n]
    if not offenders:
        logger.info("Every declared output is fully backed up for every sample.")
        return
    logger.info("Top %d outputs by missing count:", len(offenders))
    for r in offenders:
        logger.info(
            "  %-30s missing=%d/%d (%s%%)  dir=%s",
            r["software_name"], r["n_missing"], r["total_samples"],
            r["missing_pct"], r["dirname"],
        )


def _check_species_sanity(doc, expected_species_full):
    """Warn if the doc's top species_prediction disagrees with the profile's species."""
    if not expected_species_full:
        return
    preds = doc.get("species_prediction") or []
    if not preds:
        return
    top = preds[0]
    name = top.get("scientific_name") if isinstance(top, dict) else None
    if name and name != expected_species_full:
        logger.warning(
            "Species mismatch for %s: top prediction=%s, profile expects=%s",
            doc.get("sample_id"), name, expected_species_full,
        )


def _glob_matches(search_dir, prefix, mask, ext):
    """Return absolute paths in `search_dir` whose names match `<prefix><mask><ext>`.

    If `mask` contains a `*` the match is via fnmatch; otherwise it's a literal
    equality check on the full filename.
    """
    if not prefix or not os.path.isdir(search_dir):
        return []
    if "*" in mask:
        pattern = f"{prefix}{mask}{ext}"
        return [
            os.path.join(search_dir, name)
            for name in os.listdir(search_dir)
            if fnmatch.fnmatchcase(name, pattern)
        ]
    target = f"{prefix}{mask}{ext}"
    full = os.path.join(search_dir, target)
    return [full] if os.path.isfile(full) else []


def _format_glob(prefix, mask, ext):
    """Render the glob the matcher would have used, for diagnostic CSV output.

    `ext` may be a string or a list of strings (multi-extension OR-match). For
    lists, join the variants with `|` so the CSV shows every alternative tried.
    """
    if isinstance(ext, (list, tuple)):
        return "|".join(f"{prefix}{mask}{e}" for e in ext)
    return f"{prefix}{mask}{ext}"


def _as_list(value):
    """Normalise scalar-or-list to a list."""
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]


def _versions_sample_id(filename, sample_ids_desc):
    """Return the known sample_id that prefixes a `<sid>_<...>_versions.yml` filename, or None.

    JASEN writes per-process versions metadata as `<sample>_<process_path>_versions.yml`.
    Because a sample_id can itself contain underscores, we longest-prefix-match against
    the supplied sample_ids list (sorted descending by length).
    """
    if not filename.endswith("_versions.yml"):
        return None
    for sid in sample_ids_desc:
        if filename.startswith(f"{sid}_"):
            return sid
    return None


def _collect_assembly_paths(samples, backup_dir, species, profile):
    """List backed-up FASTA assemblies for samples where sample_name != sample_id.

    Walks `<backup-dir>/<species>/fasta/` once, then per filtered sample checks
    each assembler's expected filename against the listing. One row per existing
    `<sample_id>_<assembler>.fasta`. Samples with `sample_name == sample_id` are
    skipped (complement of the review.csv `name_equals_id` filter).
    """
    fasta_dir = os.path.join(backup_dir, species, "fasta")
    if not os.path.isdir(fasta_dir):
        return []
    available = set(os.listdir(fasta_dir))
    rows = []
    for doc in samples:
        sid = doc.get("sample_id")
        name = doc.get("sample_name", "")
        if not sid or sid == name:
            continue
        for assembler in ASSEMBLERS:
            fname = f"{sid}_{assembler}.fasta"
            if fname in available:
                rows.append({
                    "sample_id": sid,
                    "sample_name": name,
                    "lims_id": doc.get("lims_id", ""),
                    "profile": profile,
                    "assembler": assembler,
                    "assembly_path": os.path.join(fasta_dir, fname),
                })
    return rows


def _detect_sample_quirks(samples, profile):
    """Return one row per (sample, reason) for samples that warrant human attention.

    Reasons emitted:
      - `name_equals_id` — the sample's `sample_name` equals its `sample_id`,
        typically meaning the human-readable name was never set on import.
      - `duplicate_sample_id` — this `sample_id` appears more than once in the
        queried set (Mongo doesn't enforce uniqueness on this field by default).
      - `duplicate_sample_name` — this `sample_name` appears more than once.

    A sample can appear in multiple rows if more than one reason applies.
    """
    id_counts = Counter(s.get("sample_id") for s in samples if s.get("sample_id"))
    name_counts = Counter(s.get("sample_name") for s in samples if s.get("sample_name"))
    rows = []
    for doc in samples:
        sid = doc.get("sample_id")
        if not sid:
            continue
        name = doc.get("sample_name", "")
        lims = doc.get("lims_id", "")
        base = {"sample_id": sid, "sample_name": name, "lims_id": lims, "profile": profile}
        if sid == name:
            rows.append({**base, "reason": "name_equals_id"})
        if id_counts[sid] > 1:
            rows.append({**base, "reason": "duplicate_sample_id"})
        if name and name_counts[name] > 1:
            rows.append({**base, "reason": "duplicate_sample_name"})
    return rows


def _write_csv(path, rows, fieldnames):
    """Write `rows` to `path` as CSV with the supplied header."""
    with open(path, "w", encoding="utf-8", newline="") as fout:
        writer = csv.DictWriter(fout, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
