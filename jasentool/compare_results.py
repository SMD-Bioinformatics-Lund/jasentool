"""Compare a JASEN TB run's tb-profiler and mykrobe results with a Bonsai v2 database.

For every sample with a tb-profiler JSON or mykrobe CSV under
`<input-dir>/mtuberculosis/`, the run's results are compared with the sample's Bonsai
v2 (2.1.0, 2.1.0-patch1 or 2.1.1) document: lineage, number of variants, which variants
are called and, for tb-profiler, the tbdb database. The run files are parsed the way
bonsai-prp parsed them for Bonsai v2 (1.3.3 for 2.1.0, 1.6.1 for 2.1.1; both parse
tb-profiler and mykrobe the same way), so both sides describe each variant the same way.

tb-profiler variants are matched on genome position, ref and alt; a gene name that
differs for the same variant (e.g. a fabG1/inhA rename) is reported as `variant_gene`.
mykrobe variants are matched on gene, position, ref and alt.
"""

import csv
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime

from jasentool.check_backup import _as_list, _write_csv
from jasentool.config import get_profile
from jasentool.database import Database
from jasentool.log import get_logger

logger = get_logger(__name__)

PROFILE = "mycobacterium_tuberculosis"
SOFTWARES = ("tbprofiler", "mykrobe")
_RUN_OUTPUTS = {"tbprofiler": "tbprofiler_json", "mykrobe": "mykrobe"}
_TBPROFILER_CATEGORIES = ("dr_variants", "other_variants", "qc_fail_variants")
_MYKROBE_DB_NAME = "mykrobe-predictor"
_MYKROBE_CALL = re.compile(
    r"(?P<gene>.+)_(?P<aa_change>.+)-(?P<dna_change>.+)"
    r":(?P<ref_depth>\d+):(?P<alt_depth>\d+):(?P<conf>\d+)",
    re.IGNORECASE,
)

SUMMARY_FIELDS = [
    "sample_id", "software", "status",
    "bonsai_lineage", "run_lineage", "bonsai_sublineage", "run_sublineage",
    "bonsai_n_variants", "run_n_variants", "variants_only_in_bonsai", "variants_only_in_run",
    "bonsai_database", "run_database",
]
DIFFERENCE_FIELDS = ["sample_id", "software", "field", "bonsai_value", "run_value"]


@dataclass(frozen=True)
class Variant:
    gene: str | None
    pos: int | None
    ref: str | None
    alt: str | None
    change: str | None = None

    def label(self):
        text = f"{self.gene}:{self.pos}{self.ref}>{self.alt}"
        return f"{text} ({self.change})" if self.change else text


@dataclass
class ToolResult:
    lineage: str | None
    sublineage: str | None
    variants: list
    database: str | None = None


def _variant_key(software, variant):
    if variant.pos is None:
        return ("unparsed", variant.change)
    if software == "tbprofiler":
        return (variant.pos, variant.ref, variant.alt)
    return (variant.gene, variant.pos, variant.ref, variant.alt)


def _blank(value):
    return value is None or (isinstance(value, str) and value.strip() in {"", "NA"})


# ── run side ──────────────────────────────────────────────────────────────────

def _tbdb_version(db_version):
    """tbdb name and version as bonsai-prp 1.6.1 records it: commit, else name_<date>."""
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


def _split_change(text):
    """Split a mykrobe change such as GCT2155167GGT into (ref, pos, alt), or None."""
    first = re.search(r"\d", text)
    last = re.search(r"\d(?=[^\d]*$)", text)
    if not first or not last:
        return None
    return text[:first.start()], int(text[first.start():last.start() + 1]), text[last.start() + 1:]


def _mykrobe_variant(call):
    """One mykrobe variant call, with codons reduced to the changed bases as bonsai-prp does."""
    match = _MYKROBE_CALL.search(call)
    dna = _split_change(match["dna_change"]) if match else None
    if not dna:
        logger.warning("Could not parse mykrobe variant %r; comparing it as written", call)
        return Variant(None, None, None, None, call)
    ref, pos, alt = dna
    aa = _split_change(match["aa_change"])
    if aa and len(aa[0]) == len(aa[2]):
        changed = [(r, a) for r, a in zip(ref, alt) if r != a]
        ref = "".join(r for r, _ in changed).upper()
        alt = "".join(a for _, a in changed).upper()
    return Variant(match["gene"], pos, ref, alt, match["aa_change"])


def parse_mykrobe(path):
    """Lineage and the variants behind resistant calls from a mykrobe CSV."""
    with open(path, newline="", encoding="utf-8") as fin:
        rows = list(csv.reader(fin))
    if len(rows) < 2:
        return ToolResult(None, None, [])
    header, body = rows[0], rows[1:]
    susceptibility = header.index("susceptibility")
    variants = []
    for row in body:
        calls = row[3]
        if row[susceptibility].upper() != "R" or _blank(calls):
            continue
        variants.extend(_mykrobe_variant(call) for call in calls.split(";"))
    lineage = body[0][header.index("lineage")] if "lineage" in header else None
    if _blank(lineage):
        return ToolResult(None, None, variants)
    return ToolResult(lineage.split(".")[0], lineage, variants)


_RUN_PARSERS = {"tbprofiler": parse_tbprofiler, "mykrobe": parse_mykrobe}


# ── Bonsai side ───────────────────────────────────────────────────────────────

def _entry(entries, entry_type, software):
    return next((e for e in entries or []
                 if e.get("type") == entry_type and e.get("software") == software), None)


def _bonsai_variant(software, variant):
    change = variant.get("hgvs_aa_change") or variant.get("hgvs_nt_change")
    if software == "mykrobe" and variant.get("ref_aa") and variant.get("alt_aa"):
        change = f"{variant['ref_aa']}>{variant['alt_aa']}"
    return Variant(variant.get("reference_sequence"), variant.get("start"),
                   variant.get("ref_nt"), variant.get("alt_nt"), change or None)


def bonsai_result(doc, software):
    """The tool's lineage, variants and (tb-profiler) tbdb from a Bonsai v2 sample doc."""
    lineage_entry = _entry(doc.get("typing_result"), "lineage", software)
    amr_entry = _entry(doc.get("element_type_result"), "AMR", software)
    if not lineage_entry and not amr_entry:
        return None
    lineage = (lineage_entry or {}).get("result") or {}
    amr = (amr_entry or {}).get("result") or {}
    database = None
    if software == "tbprofiler":
        databases = sorted(
            f"{db.get('name')} {db.get('version')}"
            for db in (doc.get("pipeline") or {}).get("softwares") or []
            if db.get("type") == "database" and db.get("name") != _MYKROBE_DB_NAME
        )
        database = "; ".join(databases) or None
    return ToolResult(
        lineage=lineage.get("main_lineage"),
        sublineage=lineage.get("sublineage"),
        variants=[_bonsai_variant(software, v) for v in amr.get("variants") or []],
        database=database,
    )


def _is_bonsai_v3(doc):
    entries = (doc.get("typing_result") or []) + (doc.get("element_type_result") or [])
    return any("analysis_type" in entry for entry in entries)


# ── comparison ────────────────────────────────────────────────────────────────

def compare(sample_id, software, bonsai, run):
    """Return (summary row, difference rows) for one sample and tool."""
    row = dict.fromkeys(SUMMARY_FIELDS, "")
    row.update(sample_id=sample_id, software=software)
    for side, result in (("bonsai", bonsai), ("run", run)):
        if result is not None:
            row[f"{side}_lineage"] = result.lineage or ""
            row[f"{side}_sublineage"] = result.sublineage or ""
            row[f"{side}_n_variants"] = len(result.variants)
            if software == "tbprofiler":
                row[f"{side}_database"] = result.database or ""
    if bonsai is None or run is None:
        row["status"] = "missing_in_bonsai" if bonsai is None else "missing_in_run"
        return row, []

    diffs = []

    def differ(field, bonsai_value, run_value):
        diffs.append({"sample_id": sample_id, "software": software, "field": field,
                      "bonsai_value": "" if bonsai_value is None else bonsai_value,
                      "run_value": "" if run_value is None else run_value})

    for field in ("lineage", "sublineage"):
        if getattr(bonsai, field) != getattr(run, field):
            differ(field, getattr(bonsai, field), getattr(run, field))
    if len(bonsai.variants) != len(run.variants):
        differ("n_variants", len(bonsai.variants), len(run.variants))

    bonsai_by_key = {_variant_key(software, v): v for v in bonsai.variants}
    run_by_key = {_variant_key(software, v): v for v in run.variants}
    only_bonsai = sorted(set(bonsai_by_key) - set(run_by_key), key=str)
    only_run = sorted(set(run_by_key) - set(bonsai_by_key), key=str)
    for key in only_bonsai:
        differ("variant", bonsai_by_key[key].label(), None)
    for key in only_run:
        differ("variant", None, run_by_key[key].label())
    for key in sorted(set(bonsai_by_key) & set(run_by_key), key=str):
        if bonsai_by_key[key].gene != run_by_key[key].gene:
            differ("variant_gene", bonsai_by_key[key].label(), run_by_key[key].label())

    if software == "tbprofiler" and bonsai.database != run.database:
        differ("database", bonsai.database, run.database)

    row["variants_only_in_bonsai"] = len(only_bonsai)
    row["variants_only_in_run"] = len(only_run)
    row["status"] = "differs" if diffs else "identical"
    return row, diffs


class CompareResults:
    """Compare a TB run tree's tb-profiler and mykrobe results with Bonsai v2."""

    def __init__(self, options):
        self.options = options
        profile = get_profile(PROFILE)
        self.species_dir = os.path.join(options.input_dir, profile["species"])
        self.outputs = {
            software: next(o for o in profile["outputs"] if o["software_name"] == name)
            for software, name in _RUN_OUTPUTS.items()
        }

    def _run_files(self):
        """{sample_id: {software: path}} for the tool outputs in the run tree."""
        files = {}
        for software, output in self.outputs.items():
            directory = os.path.join(self.species_dir, output["dirname"])
            if not os.path.isdir(directory):
                logger.warning("No %s directory at %s", software, directory)
                continue
            suffixes = [f"{output['mask']}{ext}" for ext in _as_list(output["file_ext"])]
            for name in sorted(os.listdir(directory)):
                suffix = next((x for x in suffixes if name.endswith(x) and len(name) > len(x)), None)
                if suffix:
                    files.setdefault(name[:-len(suffix)], {})[software] = os.path.join(directory, name)
        wanted = set(self.options.sample_ids or [])
        if wanted:
            for sample_id in sorted(wanted - set(files)):
                logger.warning("Sample %s has no tb-profiler or mykrobe output in %s",
                               sample_id, self.species_dir)
            files = {sid: paths for sid, paths in files.items() if sid in wanted}
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

    def _run_result(self, sample_id, software, path):
        if not path:
            return None
        try:
            return _RUN_PARSERS[software](path)
        except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
            logger.error("%s: could not parse %s output %s: %s", sample_id, software, path, exc)
            return None

    def run(self):
        """Compare every sample in the run tree and write the summary and differences."""
        files = self._run_files()
        if not files:
            logger.error("No tb-profiler or mykrobe outputs found under %s", self.species_dir)
            sys.exit(1)
        docs = self._bonsai_docs(files)
        missing = sorted(set(files) - set(docs))
        if missing:
            logger.warning("%d sample(s) not in Bonsai: %s", len(missing), ", ".join(missing))

        summary, differences = [], []
        for sample_id in sorted(files):
            doc = docs.get(sample_id)
            for software in SOFTWARES:
                bonsai = bonsai_result(doc, software) if doc else None
                run = self._run_result(sample_id, software, files[sample_id].get(software))
                if bonsai is None and run is None:
                    continue
                row, diffs = compare(sample_id, software, bonsai, run)
                summary.append(row)
                differences.extend(diffs)

        output = self.options.output_file
        os.makedirs(os.path.dirname(os.path.abspath(output)), exist_ok=True)
        differences_path = os.path.splitext(output)[0] + "_differences.csv"
        _write_csv(output, summary, SUMMARY_FIELDS)
        _write_csv(differences_path, differences, DIFFERENCE_FIELDS)
        for software in SOFTWARES:
            counts = {}
            for row in summary:
                if row["software"] == software:
                    counts[row["status"]] = counts.get(row["status"], 0) + 1
            if counts:
                logger.info("%s: %s", software,
                            ", ".join(f"{n} {status}" for status, n in sorted(counts.items())))
        logger.info("Wrote %s and %s (%d differences)", output, differences_path, len(differences))
