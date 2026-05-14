"""Cross-check MongoDB samples against the backup storage tree."""

import csv
import os
from importlib.resources import files

import yaml

from jasentool.database import Database
from jasentool.log import get_logger
from jasentool.sample_utils import alter_sample_id as compose_alter_id

logger = get_logger(__name__)

DEFAULT_CONFIG_PKG_PATH = ("jasentool", "data", "jasen_profiles.yaml")
QC_FIELD = "metadata.QC"
QC_PASS = "OK"


class CheckBackup:
    """Compare MongoDB sample documents against on-disk backup outputs."""

    def __init__(self, options):
        self.options = options
        self.profile = options.profile
        self.backup_dir = options.backup_dir
        self.output_file = options.output_file
        self.use_alter_id = options.alter_sample_id

    @staticmethod
    def load_config(config_path=None):
        """Load profile config from a path or the bundled package data."""
        if config_path:
            with open(config_path, "r", encoding="utf-8") as fin:
                return yaml.safe_load(fin)
        resource = files(DEFAULT_CONFIG_PKG_PATH[0]).joinpath(
            *DEFAULT_CONFIG_PKG_PATH[1:]
        )
        return yaml.safe_load(resource.read_text(encoding="utf-8"))

    @staticmethod
    def resolve_profile(config, profile):
        """Return (species_shortname, outputs) for `profile` or raise KeyError."""
        if profile not in config:
            raise KeyError(
                f"Profile '{profile}' not found in config. "
                f"Known profiles: {sorted(config.keys())}"
            )
        entry = config[profile]
        return entry["species"], entry.get("outputs", []) or []

    @staticmethod
    def fetch_samples(db_collection, profile_species):
        """Pull QC-OK samples for the requested species from MongoDB.

        Projects only the fields needed: `id`, `metadata.QC`, `run`,
        plus best-effort `lims_id` / `clarity_sample_id` to support
        alter-sample-id matching when present.
        """
        query = {QC_FIELD: QC_PASS}
        projection = {
            "id": 1,
            "metadata.QC": 1,
            "metadata.species": 1,
            "species": 1,
            "run": 1,
            "lims_id": 1,
            "clarity_sample_id": 1,
            "sequencing_run": 1,
        }
        docs = Database.find(db_collection, query, projection)
        return [doc for doc in docs if _matches_species(doc, profile_species)]

    def scan(self, samples, outputs, species):
        """Walk each sample × expected output, return (summary_rows, missing_rows)."""
        summary_rows = []
        missing_rows = []
        for doc in samples:
            sample_name = doc.get("id")
            alter_id = self._resolve_alter_id(doc) if self.use_alter_id else None
            expected_count = len(outputs)
            found_count = 0
            for output in outputs:
                dirname = output["dirname"]
                ext = output["ext"]
                search_dir = os.path.join(self.backup_dir, species, dirname)
                orig_matches = _glob_matches(search_dir, sample_name, ext)
                alter_matches = (
                    _glob_matches(search_dir, alter_id, ext) if alter_id else []
                )
                if orig_matches and alter_matches:
                    logger.warning(
                        "Both sample-id forms present for %s in %s (orig=%s, alter=%s)",
                        sample_name, search_dir,
                        [os.path.basename(p) for p in orig_matches],
                        [os.path.basename(p) for p in alter_matches],
                    )
                if orig_matches or alter_matches:
                    found_count += 1
                else:
                    missing_rows.append({
                        "id": sample_name,
                        "sample_name": sample_name,
                        "alter_id": alter_id or "",
                        "profile": self.profile,
                        "software_dirname": dirname,
                        "expected_glob": f"{sample_name}_*{ext}",
                        "searched_path": search_dir,
                    })
            status = "PASS" if expected_count and found_count == expected_count else "FAIL"
            summary_rows.append({
                "id": sample_name,
                "sample_name": sample_name,
                "alter_id": alter_id or "",
                "profile": self.profile,
                "expected_count": expected_count,
                "found_count": found_count,
                "status": status,
            })
        return summary_rows, missing_rows

    def _resolve_alter_id(self, doc):
        """Compose the alter-sample-id form from a sample doc, or None on missing fields."""
        lims = doc.get("lims_id") or doc.get("clarity_sample_id")
        seqrun = doc.get("sequencing_run")
        if not seqrun and doc.get("run"):
            seqrun = os.path.basename(doc["run"].rstrip("/"))
        if not lims or not seqrun:
            logger.error(
                "Cannot build alter-sample-id for %s: missing lims_id (%s) or seqrun (%s)",
                doc.get("id"), lims, seqrun,
            )
            return None
        return compose_alter_id(str(lims), str(seqrun))

    def run(self):
        """Entry point: load config, fetch samples, scan disk, write outputs."""
        config = self.load_config(self.options.config)
        species, outputs = self.resolve_profile(config, self.profile)
        if not outputs:
            logger.warning(
                "Profile '%s' has no `outputs` entries; every sample will FAIL. "
                "Populate %s before running.",
                self.profile,
                self.options.config or "the bundled jasen_profiles.yaml",
            )

        Database.initialize(self.options.db_name, uri=self.options.address)
        samples = self.fetch_samples(self.options.db_collection, species)
        logger.info(
            "%d samples found in %s/%s for species=%s",
            len(samples), self.options.db_name, self.options.db_collection, species,
        )

        summary_rows, missing_rows = self.scan(samples, outputs, species)

        _write_csv(self.output_file, summary_rows,
                   fieldnames=["id", "sample_name", "alter_id", "profile",
                               "expected_count", "found_count", "status"])
        missing_fpath = os.path.splitext(self.output_file)[0] + "_missing.csv"
        _write_csv(missing_fpath, missing_rows,
                   fieldnames=["id", "sample_name", "alter_id", "profile",
                               "software_dirname", "expected_glob", "searched_path"])

        passed = sum(1 for r in summary_rows if r["status"] == "PASS")
        failed = len(summary_rows) - passed
        logger.info("%d samples expected; %d backed up; %d not yet backed up",
                    len(summary_rows), passed, failed)


def _matches_species(doc, target_species):
    """Tolerant species match against either `species` or `metadata.species`."""
    if not target_species:
        return True
    candidates = [doc.get("species")]
    metadata = doc.get("metadata") or {}
    candidates.append(metadata.get("species") if isinstance(metadata, dict) else None)
    return any(c == target_species for c in candidates if c)


def _glob_matches(search_dir, prefix, ext):
    """Return absolute paths in `search_dir` whose names match `<prefix>_*<ext>`."""
    if not prefix or not os.path.isdir(search_dir):
        return []
    matches = []
    for name in os.listdir(search_dir):
        if name.startswith(f"{prefix}_") and name.endswith(ext):
            matches.append(os.path.join(search_dir, name))
    return matches


def _write_csv(path, rows, fieldnames):
    """Write `rows` to `path` as CSV with the supplied header."""
    with open(path, "w", encoding="utf-8", newline="") as fout:
        writer = csv.DictWriter(fout, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
