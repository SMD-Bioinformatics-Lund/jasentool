"""Cross-check cgviz QC-approved samples against a Bonsai database.

cgviz `id` corresponds to Bonsai `sample_name`, and the basename of cgviz `run`
(the sequencing run folder) to Bonsai's sequencing run: `sequencing.run_id` in
Bonsai v2, `sequencing.sequencing_run_id` in v3.
"""

import os
from collections import Counter

from jasentool.check_backup import _write_csv
from jasentool.database import Database
from jasentool.log import get_logger

logger = get_logger(__name__)

MISSING_FIELDS = ["sample_name", "cgviz_run", "bonsai_runs", "reason"]
UNAPPROVED_FIELDS = [
    "sample_id", "sample_name", "lims_id", "bonsai_run",
    "cgviz_approved_runs", "cgviz_qc", "reason",
]


def _clean(value):
    """Strip an identifier, treating blanks as absent."""
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _cgviz_run(doc):
    run = _clean(doc.get("run"))
    return os.path.basename(run.rstrip("/")) if run else None


def _bonsai_run(doc):
    sequencing = doc.get("sequencing") or {}
    return _clean(sequencing.get("run_id") or sequencing.get("sequencing_run_id"))


def _join(values):
    return ";".join(sorted(value or "" for value in values))


def compare(cgviz_docs, bonsai_docs):
    """Return (missing_from_bonsai, bonsai_unapproved) rows.

    missing_from_bonsai: each QC-approved cgviz (sample, run) with no Bonsai sample
    of that name and run. bonsai_unapproved: each Bonsai sample that doesn't match an
    approved cgviz (sample, run).
    """
    approved = {}
    qc_seen = {}
    for doc in cgviz_docs:
        name = _clean(doc.get("id"))
        if not name:
            continue
        qc = (doc.get("metadata") or {}).get("QC")
        qc_seen.setdefault(name, set()).add(str(qc))
        if qc == "OK":
            approved.setdefault(name, set()).add(_cgviz_run(doc))

    bonsai_runs = {}
    for doc in bonsai_docs:
        bonsai_runs.setdefault(_clean(doc.get("sample_name")), set()).add(_bonsai_run(doc))

    missing = []
    for name in sorted(approved):
        present = bonsai_runs.get(name, set())
        for run in sorted(approved[name], key=lambda value: value or ""):
            if run in present:
                continue
            missing.append({
                "sample_name": name,
                "cgviz_run": run or "",
                "bonsai_runs": _join(present),
                "reason": "run_mismatch" if present else "missing",
            })

    unapproved = []
    for doc in sorted(bonsai_docs, key=lambda d: (d.get("sample_name") or "", d.get("sample_id") or "")):
        name = _clean(doc.get("sample_name"))
        run = _bonsai_run(doc)
        if name in approved:
            if run in approved[name]:
                continue
            reason = "wrong_run"
        elif name in qc_seen:
            reason = "not_approved"
        else:
            reason = "not_in_cgviz"
        unapproved.append({
            "sample_id": doc.get("sample_id", ""),
            "sample_name": name or "",
            "lims_id": doc.get("lims_id") or "",
            "bonsai_run": run or "",
            "cgviz_approved_runs": _join(approved.get(name, set())),
            "cgviz_qc": _join(qc_seen.get(name, set())),
            "reason": reason,
        })
    return missing, unapproved


class CompareBonsai:
    """Compare cgviz QC-approved samples with the Bonsai samples of one profile."""

    def __init__(self, options):
        self.options = options

    def _fetch(self):
        Database.initialize(self.options.cgviz_db_name, uri=self.options.cgviz_address)
        cgviz_docs = Database.find(
            self.options.cgviz_db_collection, {}, {"_id": 0, "id": 1, "run": 1, "metadata.QC": 1},
        )
        Database.initialize(self.options.bonsai_db_name, uri=self.options.bonsai_address)
        bonsai_docs = Database.find(
            self.options.bonsai_db_collection,
            {"pipeline.analysis_profile": self.options.bonsai_profile},
            {
                "_id": 0, "sample_id": 1, "sample_name": 1, "lims_id": 1,
                "sequencing.run_id": 1, "sequencing.sequencing_run_id": 1,
            },
        )
        return cgviz_docs, bonsai_docs

    def run(self):
        """Fetch both databases, compare, and write the two report CSVs."""
        cgviz_docs, bonsai_docs = self._fetch()
        missing, unapproved = compare(cgviz_docs, bonsai_docs)

        stem = os.path.splitext(self.options.output_file)[0]
        missing_fpath = f"{stem}_missing_from_bonsai.csv"
        unapproved_fpath = f"{stem}_bonsai_unapproved.csv"
        _write_csv(missing_fpath, missing, MISSING_FIELDS)
        _write_csv(unapproved_fpath, unapproved, UNAPPROVED_FIELDS)

        logger.info(
            "%d cgviz samples, %d Bonsai samples for profile=%s",
            len(cgviz_docs), len(bonsai_docs), self.options.bonsai_profile,
        )
        logger.info(
            "%d approved cgviz sample-runs not in Bonsai %s (see %s)",
            len(missing), dict(Counter(row["reason"] for row in missing)), missing_fpath,
        )
        logger.info(
            "%d Bonsai samples without an approved cgviz sample-run %s (see %s)",
            len(unapproved), dict(Counter(row["reason"] for row in unapproved)), unapproved_fpath,
        )
