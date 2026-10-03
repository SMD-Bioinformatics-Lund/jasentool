"""Tests for jasentool.compare_bonsai (identify-missing cgviz vs Bonsai comparison)."""
import csv

import pytest
from click.testing import CliRunner

from jasentool.cli import cli
from jasentool.compare_bonsai import compare
from jasentool.database import Database


def _cgviz(sample_id, run, qc="OK"):
    return {"id": sample_id, "run": f"/fs1/seqdata/NovaSeq/{run}", "metadata": {"QC": qc}}


def _bonsai(sample_id, sample_name, run, field="run_id"):
    return {"sample_id": sample_id, "sample_name": sample_name, "sequencing": {field: run}}


CGVIZ = [
    _cgviz("S1", "240101_RUN"),
    _cgviz("S2", "240102_RUN/"),
    _cgviz("S3", "240103_R2"),
    _cgviz("S4", "240104_X"),
    _cgviz("S5", "240105_RUN", qc="fail"),
]
BONSAI = [
    _bonsai("s1", "S1", "240101_RUN"),
    _bonsai("s3_r1", "S3", "240103_R1"),
    _bonsai("s3_r2", "S3", "240103_R2"),
    _bonsai("s4", "S4", "240104_Y"),
    _bonsai("s5", "S5", "240105_RUN"),
    _bonsai("s6", "S6", "240106_RUN"),
]


def test_compare_reports_each_direction():
    missing, unapproved = compare(CGVIZ, BONSAI)

    assert missing == [
        {"sample_name": "S2", "cgviz_run": "240102_RUN", "bonsai_runs": "", "reason": "missing"},
        {"sample_name": "S4", "cgviz_run": "240104_X", "bonsai_runs": "240104_Y",
         "reason": "run_mismatch"},
    ]
    assert [(row["sample_id"], row["reason"]) for row in unapproved] == [
        ("s3_r1", "wrong_run"),
        ("s4", "wrong_run"),
        ("s5", "not_approved"),
        ("s6", "not_in_cgviz"),
    ]
    s3_r1 = unapproved[0]
    assert s3_r1["bonsai_run"] == "240103_R1"
    assert s3_r1["cgviz_approved_runs"] == "240103_R2"
    assert unapproved[2]["cgviz_qc"] == "fail"


def test_compare_reads_bonsai_v3_run_field():
    missing, unapproved = compare(
        [_cgviz("S1", "240101_RUN")],
        [_bonsai("s1", "S1", "240101_RUN", field="sequencing_run_id")],
    )
    assert missing == [] and unapproved == []


class FakeMongo:
    """Two databases behind one Database facade, switched by initialize()."""

    def __init__(self, docs_by_db):
        self.docs_by_db = docs_by_db
        self.current = None
        self.queries = {}

    def initialize(self, db_name, uri=None):  # noqa: ARG002
        self.current = db_name

    def find(self, collection, query, fields):  # noqa: ARG002
        self.queries[self.current] = (collection, query)
        return self.docs_by_db[self.current]


def _patch(monkeypatch):
    fake = FakeMongo({"cgviz": CGVIZ, "bonsai": BONSAI})
    monkeypatch.setattr(Database, "initialize", fake.initialize)
    monkeypatch.setattr(Database, "find", fake.find)
    return fake


@pytest.mark.parametrize("db_flags", [
    [],
    ["--cgviz-db-name", "cgviz", "--cgviz-db-collection", "sample"],
    ["--db-name", "cgviz", "--db-collection", "sample"],
])
def test_identify_missing_writes_bonsai_comparison(tmp_path, monkeypatch, db_flags):
    fake = _patch(monkeypatch)

    result = CliRunner().invoke(cli, [
        "identify-missing", "-o", str(tmp_path / "report.csv"), "--compare-bonsai", *db_flags,
    ])

    assert result.exit_code == 0, result.output
    assert fake.queries["cgviz"][0] == "sample"
    assert fake.queries["bonsai"] == ("sample", {"pipeline.analysis_profile": "staphylococcus_aureus"})
    with open(tmp_path / "report_missing_from_bonsai.csv", encoding="utf-8") as fin:
        assert [row["sample_name"] for row in csv.DictReader(fin)] == ["S2", "S4"]
    with open(tmp_path / "report_bonsai_unapproved.csv", encoding="utf-8") as fin:
        assert [row["reason"] for row in csv.DictReader(fin)] == [
            "wrong_run", "wrong_run", "not_approved", "not_in_cgviz",
        ]


def test_identify_missing_skips_bonsai_comparison_by_default(tmp_path, monkeypatch):
    fake = _patch(monkeypatch)

    result = CliRunner().invoke(cli, ["identify-missing", "-o", str(tmp_path / "report.csv")])

    assert result.exit_code == 0, result.output
    assert "bonsai" not in fake.queries
    assert not (tmp_path / "report_missing_from_bonsai.csv").exists()
