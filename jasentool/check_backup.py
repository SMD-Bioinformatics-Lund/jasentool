"""Cross-check Bonsai samples against the backup storage tree."""

import csv
import fnmatch
import os

from jasentool.config import get_profile
from jasentool.database import Database
from jasentool.log import get_logger

logger = get_logger(__name__)


class CheckBackup:
    """Compare Bonsai sample documents against on-disk backup outputs."""

    def __init__(self, options):
        self.options = options
        self.profile = options.profile
        self.backup_dir = options.backup_dir
        self.output_file = options.output_file

    @staticmethod
    def fetch_samples(db_collection, profile_entry):
        """Pull samples for the requested species from Bonsai.

        Filters by species (matched against either the short form `saureus`
        or the profile-name-with-spaces form `staphylococcus aureus`). No
        QC filter — Bonsai is assumed to be the curated set already.
        """
        accepted_species = {
            profile_entry["species"],
            profile_entry["profile"].replace("_", " "),
        }
        projection = {
            "_id": 0,
            "sample_id": 1,
            "sample_name": 1,
            "species": 1,
            "metadata.species": 1,
        }
        docs = Database.find(db_collection, {}, projection)
        return [doc for doc in docs if _matches_species(doc, accepted_species)]

    def scan(self, samples, outputs, species):
        """Walk each sample x expected output, return (summary_rows, missing_rows)."""
        summary_rows = []
        missing_rows = []
        for doc in samples:
            sample_id = doc.get("sample_id")
            if not sample_id:
                logger.warning("Skipping bonsai doc with no sample_id: %s", doc)
                continue
            required_total = sum(1 for o in outputs if o.get("required", True))
            required_found = 0
            optional_total = len(outputs) - required_total
            optional_found = 0
            for output in outputs:
                software = output["software_name"]
                dirname = output["dirname"]
                mask = output.get("mask", "")
                ext = output["file_ext"]
                required = output.get("required", True)
                search_dir = os.path.join(self.backup_dir, species, dirname)
                matches = _glob_matches(search_dir, sample_id, mask, ext)
                if matches:
                    if required:
                        required_found += 1
                    else:
                        optional_found += 1
                else:
                    missing_rows.append({
                        "sample_id": sample_id,
                        "sample_name": doc.get("sample_name", ""),
                        "profile": self.profile,
                        "software_name": software,
                        "software_dirname": dirname,
                        "expected_glob": _format_glob(sample_id, mask, ext),
                        "searched_path": search_dir,
                        "required": str(required),
                    })
            status = "PASS" if required_total and required_found == required_total else "FAIL"
            summary_rows.append({
                "sample_id": sample_id,
                "sample_name": doc.get("sample_name", ""),
                "profile": self.profile,
                "required_expected": required_total,
                "required_found": required_found,
                "optional_expected": optional_total,
                "optional_found": optional_found,
                "status": status,
            })
        return summary_rows, missing_rows

    def run(self):
        """Entry point: resolve profile, fetch samples, scan disk, write outputs."""
        profile_entry = get_profile(self.profile)
        species = profile_entry["species"]
        outputs = profile_entry.get("outputs", []) or []
        if not outputs:
            logger.warning(
                "Profile '%s' has no outputs declared in jasentool.config; every "
                "sample will FAIL.", self.profile,
            )

        Database.initialize(self.options.db_name, uri=self.options.address)
        samples = self.fetch_samples(self.options.db_collection, profile_entry)
        logger.info(
            "%d bonsai samples for species=%s (from %s/%s)",
            len(samples), species, self.options.db_name, self.options.db_collection,
        )

        summary_rows, missing_rows = self.scan(samples, outputs, species)

        _write_csv(self.output_file, summary_rows,
                   fieldnames=["sample_id", "sample_name", "profile",
                               "required_expected", "required_found",
                               "optional_expected", "optional_found", "status"])
        missing_fpath = os.path.splitext(self.output_file)[0] + "_missing.csv"
        _write_csv(missing_fpath, missing_rows,
                   fieldnames=["sample_id", "sample_name", "profile",
                               "software_name", "software_dirname",
                               "expected_glob", "searched_path", "required"])

        passed = sum(1 for r in summary_rows if r["status"] == "PASS")
        failed = len(summary_rows) - passed
        logger.info("%d samples expected; %d backed up; %d not yet backed up",
                    len(summary_rows), passed, failed)


def _matches_species(doc, accepted_species):
    """Return True if the doc's species (top-level or under metadata) is in `accepted_species`."""
    candidates = [doc.get("species")]
    metadata = doc.get("metadata") or {}
    if isinstance(metadata, dict):
        candidates.append(metadata.get("species"))
    return any(c in accepted_species for c in candidates if c)


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
    """Render the glob the matcher would have used, for diagnostic CSV output."""
    return f"{prefix}{mask}{ext}"


def _write_csv(path, rows, fieldnames):
    """Write `rows` to `path` as CSV with the supplied header."""
    with open(path, "w", encoding="utf-8", newline="") as fout:
        writer = csv.DictWriter(fout, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
