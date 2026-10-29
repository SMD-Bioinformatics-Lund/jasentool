"""Compare a JASEN TB run's tb-profiler results with a Bonsai v2 database.

For every sample with a tb-profiler JSON under `<input-dir>/mtuberculosis/`, the run's
results are compared with the sample's Bonsai v2 (2.1.0, 2.1.0-patch1 or 2.1.1)
document: lineage, number of variants, which variants are called and the tbdb database.
The run files are parsed the way bonsai-prp parsed them for Bonsai v2 (1.3.3 for 2.1.0,
1.6.1 for 2.1.1; both parse tb-profiler the same way), so both sides describe each
variant the same way.

Variants are matched on genome position, ref and alt; a gene name that differs for the
same variant (e.g. a fabG1/inhA rename) is reported as `variant_gene`.
"""

import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime

from jasentool.check_backup import _as_list, _write_csv
from jasentool.config import get_profile
from jasentool.database import Database
from jasentool.log import get_logger

logger = get_logger(__name__)

PROFILE = "mycobacterium_tuberculosis"
SOFTWARE = "tbprofiler"
_RUN_OUTPUT = "tbprofiler_json"
_TBPROFILER_CATEGORIES = ("dr_variants", "other_variants", "qc_fail_variants")
_MYKROBE_DB_NAME = "mykrobe-predictor"

SUMMARY_FIELDS = [
    "sample_id", "status",
    "bonsai_lineage", "run_lineage", "bonsai_sublineage", "run_sublineage",
    "bonsai_n_variants", "run_n_variants", "variants_only_in_bonsai", "variants_only_in_run",
    "bonsai_database", "run_database",
]
DIFFERENCE_FIELDS = ["sample_id", "field", "bonsai_value", "run_value"]


@dataclass(frozen=True)
class Variant:
    gene: str | None
    pos: int | None
    ref: str | None
    alt: str | None
    change: str | None = None

    @property
    def key(self):
        return (self.pos, self.ref, self.alt)

    def label(self):
        text = f"{self.gene}:{self.pos}{self.ref}>{self.alt}"
        return f"{text} ({self.change})" if self.change else text


@dataclass
class ToolResult:
    lineage: str | None
    sublineage: str | None
    variants: list
    database: str | None = None


# ── run side ──────────────────────────────────────────────────────────────────

def _tbdb_version(db_version):
    """tbdb name and version as bonsai-prp records it: commit, else name_<date>."""
    name = db_version.get("name")
    if "commit" in db_version:
        return f"{name} {db_version['commit']}"
    date = db_version.get("Date", "")
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%a %b %d %H:%M:%S %Y %z"):
        try:
            date = datetime.strptime(date, fmt).date().isoformat()
            break
        except ValueError:
            continue
    return f"{name} {name}_{date}"


def parse_tbprofiler(path):
    """Lineage, variants (all three categories) and tbdb version from a tb-profiler JSON."""
    with open(path, encoding="utf-8") as fin:
        data = json.load(fin)
    variants = [
        Variant(hit.get("gene_name"), int(hit["pos"]), hit.get("ref"), hit.get("alt"),
                hit.get("protein_change") or hit.get("nucleotide_change") or None)
        for category in _TBPROFILER_CATEGORIES for hit in data.get(category) or []
    ]
    db_version = (data.get("pipeline") or {}).get("db_version")
    return ToolResult(
        lineage=data.get("main_lineage"),
        sublineage=data.get("sub_lineage"),
        variants=variants,
        database=_tbdb_version(db_version) if db_version else None,
    )


# ── Bonsai side ───────────────────────────────────────────────────────────────

def _entry(entries, entry_type):
    return next((e for e in entries or []
                 if e.get("type") == entry_type and e.get("software") == SOFTWARE), None)


def _bonsai_variant(variant):
    return Variant(variant.get("reference_sequence"), variant.get("start"),
                   variant.get("ref_nt"), variant.get("alt_nt"),
                   variant.get("hgvs_aa_change") or variant.get("hgvs_nt_change") or None)


def bonsai_result(doc):
    """tb-profiler's lineage, variants and tbdb from a Bonsai v2 sample doc."""
    lineage_entry = _entry(doc.get("typing_result"), "lineage")
    amr_entry = _entry(doc.get("element_type_result"), "AMR")
    if not lineage_entry and not amr_entry:
        return None
    lineage = (lineage_entry or {}).get("result") or {}
    amr = (amr_entry or {}).get("result") or {}
    databases = sorted(
        f"{db.get('name')} {db.get('version')}"
        for db in (doc.get("pipeline") or {}).get("softwares") or []
        if db.get("type") == "database" and db.get("name") != _MYKROBE_DB_NAME
    )
    return ToolResult(
        lineage=lineage.get("main_lineage"),
        sublineage=lineage.get("sublineage"),
        variants=[_bonsai_variant(v) for v in amr.get("variants") or []],
        database="; ".join(databases) or None,
    )


def _is_bonsai_v3(doc):
    entries = (doc.get("typing_result") or []) + (doc.get("element_type_result") or [])
    return any("analysis_type" in entry for entry in entries)


# ── comparison ────────────────────────────────────────────────────────────────

def compare(sample_id, bonsai, run):
    """Return (summary row, difference rows) for one sample."""
    row = dict.fromkeys(SUMMARY_FIELDS, "")
    row["sample_id"] = sample_id
    for side, result in (("bonsai", bonsai), ("run", run)):
        if result is not None:
            row[f"{side}_lineage"] = result.lineage or ""
            row[f"{side}_sublineage"] = result.sublineage or ""
            row[f"{side}_n_variants"] = len(result.variants)
            row[f"{side}_database"] = result.database or ""
    if bonsai is None or run is None:
        row["status"] = "missing_in_bonsai" if bonsai is None else "missing_in_run"
        return row, []

    diffs = []

    def differ(field, bonsai_value, run_value):
        diffs.append({"sample_id": sample_id, "field": field,
                      "bonsai_value": "" if bonsai_value is None else bonsai_value,
                      "run_value": "" if run_value is None else run_value})

    for field in ("lineage", "sublineage"):
        if getattr(bonsai, field) != getattr(run, field):
            differ(field, getattr(bonsai, field), getattr(run, field))
    if len(bonsai.variants) != len(run.variants):
        differ("n_variants", len(bonsai.variants), len(run.variants))

    bonsai_by_key = {v.key: v for v in bonsai.variants}
    run_by_key = {v.key: v for v in run.variants}
    only_bonsai = sorted(set(bonsai_by_key) - set(run_by_key), key=str)
    only_run = sorted(set(run_by_key) - set(bonsai_by_key), key=str)
    for key in only_bonsai:
        differ("variant", bonsai_by_key[key].label(), None)
    for key in only_run:
        differ("variant", None, run_by_key[key].label())
    for key in sorted(set(bonsai_by_key) & set(run_by_key), key=str):
        if bonsai_by_key[key].gene != run_by_key[key].gene:
            differ("variant_gene", bonsai_by_key[key].label(), run_by_key[key].label())

    if bonsai.database != run.database:
        differ("database", bonsai.database, run.database)

    row["variants_only_in_bonsai"] = len(only_bonsai)
    row["variants_only_in_run"] = len(only_run)
    row["status"] = "differs" if diffs else "identical"
    return row, diffs


class CompareResults:
    """Compare a TB run tree's tb-profiler results with Bonsai v2."""

    def __init__(self, options):
        self.options = options
        profile = get_profile(PROFILE)
        output = next(o for o in profile["outputs"] if o["software_name"] == _RUN_OUTPUT)
        self.run_dir = os.path.join(options.input_dir, profile["species"], output["dirname"])
        self.suffixes = [f"{output['mask']}{ext}" for ext in _as_list(output["file_ext"])]

    def _run_files(self):
        """{sample_id: path} for the tb-profiler JSONs in the run tree."""
        files = {}
        if os.path.isdir(self.run_dir):
            for name in sorted(os.listdir(self.run_dir)):
                suffix = next((x for x in self.suffixes
                               if name.endswith(x) and len(name) > len(x)), None)
                if suffix:
                    files[name[:-len(suffix)]] = os.path.join(self.run_dir, name)
        wanted = set(self.options.sample_ids or [])
        if wanted:
            for sample_id in sorted(wanted - set(files)):
                logger.warning("Sample %s has no tb-profiler output in %s", sample_id, self.run_dir)
            files = {sid: path for sid, path in files.items() if sid in wanted}
        return files

    def _bonsai_docs(self, sample_ids):
        Database.initialize(self.options.db_name, uri=self.options.address)
        projection = {"_id": 0, "sample_id": 1, "typing_result": 1,
                      "element_type_result": 1, "pipeline.softwares": 1}
        docs = {}
        for doc in Database.find(self.options.db_collection,
                                 {"sample_id": {"$in": sorted(sample_ids)}}, projection):
            if _is_bonsai_v3(doc):
                logger.error("Sample %s is in Bonsai v3 format; compare-results reads "
                             "Bonsai v2 (2.1.x) databases only", doc["sample_id"])
                sys.exit(1)
            docs.setdefault(doc["sample_id"], doc)
        return docs

    def _run_result(self, sample_id, path):
        try:
            return parse_tbprofiler(path)
        except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
            logger.error("%s: could not parse tb-profiler output %s: %s", sample_id, path, exc)
            return None

    def run(self):
        """Compare every sample in the run tree and write the summary and differences."""
        files = self._run_files()
        if not files:
            logger.error("No tb-profiler outputs found in %s", self.run_dir)
            sys.exit(1)
        docs = self._bonsai_docs(files)
        missing = sorted(set(files) - set(docs))
        if missing:
            logger.warning("%d sample(s) not in Bonsai: %s", len(missing), ", ".join(missing))

        summary, differences = [], []
        for sample_id in sorted(files):
            doc = docs.get(sample_id)
            bonsai = bonsai_result(doc) if doc else None
            row, diffs = compare(sample_id, bonsai, self._run_result(sample_id, files[sample_id]))
            summary.append(row)
            differences.extend(diffs)

        output = self.options.output_file
        os.makedirs(os.path.dirname(os.path.abspath(output)), exist_ok=True)
        differences_path = os.path.splitext(output)[0] + "_differences.csv"
        _write_csv(output, summary, SUMMARY_FIELDS)
        _write_csv(differences_path, differences, DIFFERENCE_FIELDS)
        counts = {}
        for row in summary:
            counts[row["status"]] = counts.get(row["status"], 0) + 1
        logger.info("tb-profiler: %s",
                    ", ".join(f"{n} {status}" for status, n in sorted(counts.items())))
        logger.info("Wrote %s and %s (%d differences)", output, differences_path, len(differences))
