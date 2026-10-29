import copy
import csv
import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from jasentool.cli import cli
from jasentool.compare_results import _tbdb_version
from jasentool.database import Database

FIXTURES = Path(__file__).parent / "fixtures" / "mtuberculosis"
BONSAI_DOC = json.loads((FIXTURES / "bonsai_v2_sample.json").read_text())
runner = CliRunner()


class FakeBonsai:
    def __init__(self, docs):
        self.docs = docs

    def find(self, collection, query, fields):
        wanted = set(query["sample_id"]["$in"])
        return [doc for doc in self.docs if doc["sample_id"] in wanted]


def _run_tree(tmp_path, sample_ids=("s1",), tbprofiler_edit=None):
    root = tmp_path / "run"
    tbp_dir = root / "mtuberculosis" / "tbprofiler_mergedb"
    tbp_dir.mkdir(parents=True)
    for sample_id in sample_ids:
        data = json.loads((FIXTURES / "tbprofiler.json").read_text())
        if tbprofiler_edit:
            tbprofiler_edit(data)
        (tbp_dir / f"{sample_id}_tbprofiler.json").write_text(json.dumps(data))
    return root


def _compare(monkeypatch, tmp_path, root, docs, *extra):
    monkeypatch.setattr(Database, "initialize", lambda *a, **kw: None)
    monkeypatch.setattr(Database, "find", FakeBonsai(docs).find)
    out = tmp_path / "out" / "compare.csv"
    result = runner.invoke(cli, ["compare-results", "--input-dir", str(root), "-o", str(out), *extra])
    summary = list(csv.DictReader(out.open())) if out.exists() else []
    diffs_path = out.with_name("compare_differences.csv")
    diffs = list(csv.DictReader(diffs_path.open())) if diffs_path.exists() else []
    return result, {r["sample_id"]: r for r in summary}, diffs


def test_run_parsed_like_bonsai_is_identical(monkeypatch, tmp_path):
    result, summary, diffs = _compare(monkeypatch, tmp_path, _run_tree(tmp_path), [BONSAI_DOC])

    assert result.exit_code == 0, result.output
    assert summary["s1"]["status"] == "identical"
    assert summary["s1"]["run_sublineage"] == "lineage2.2.1"
    assert summary["s1"]["run_n_variants"] == "66"
    assert summary["s1"]["run_database"] == (
        "converged_who_fohm_tbdb converged_who_fohm_tbdb_2024-05-08")
    assert diffs == []


def test_differences_are_reported(monkeypatch, tmp_path):
    def edit(data):
        data["sub_lineage"] = "lineage2.2.2"
        data["dr_variants"][0]["gene_name"] = "renamed"
        data["other_variants"].pop(0)
        data["pipeline"]["db_version"] = {"name": "tbdb", "commit": "abc123"}

    result, summary, diffs = _compare(
        monkeypatch, tmp_path, _run_tree(tmp_path, tbprofiler_edit=edit), [BONSAI_DOC])

    assert result.exit_code == 0, result.output
    row = summary["s1"]
    assert row["status"] == "differs"
    assert (row["variants_only_in_bonsai"], row["variants_only_in_run"]) == ("1", "0")
    fields = {d["field"]: d for d in diffs}
    assert set(fields) == {"sublineage", "n_variants", "variant", "variant_gene", "database"}
    assert fields["sublineage"]["run_value"] == "lineage2.2.2"
    assert fields["n_variants"]["bonsai_value"] == "66" and fields["n_variants"]["run_value"] == "65"
    assert fields["variant"]["bonsai_value"].startswith("gyrA:7362G>C")
    assert fields["variant_gene"]["run_value"].startswith("renamed:761104")
    assert fields["database"]["run_value"] == "tbdb abc123"


def test_mykrobe_results_in_bonsai_are_ignored(monkeypatch, tmp_path):
    doc = copy.deepcopy(BONSAI_DOC)
    next(e for e in doc["typing_result"] if e["software"] == "mykrobe")["result"]["sublineage"] = "lineage9"
    next(e for e in doc["element_type_result"] if e["software"] == "mykrobe")["result"]["variants"] = []

    result, summary, diffs = _compare(monkeypatch, tmp_path, _run_tree(tmp_path), [doc])

    assert result.exit_code == 0, result.output
    assert summary["s1"]["status"] == "identical"
    assert diffs == []


def test_samples_missing_from_bonsai(monkeypatch, tmp_path):
    root = _run_tree(tmp_path, sample_ids=("s1", "s2"))

    result, summary, _ = _compare(monkeypatch, tmp_path, root, [BONSAI_DOC])

    assert result.exit_code == 0, result.output
    assert summary["s1"]["status"] == "identical"
    assert summary["s2"]["status"] == "missing_in_bonsai"


def test_sample_id_filter(monkeypatch, tmp_path):
    root = _run_tree(tmp_path, sample_ids=("s1", "s2"))

    result, summary, _ = _compare(monkeypatch, tmp_path, root, [BONSAI_DOC], "--sample-id", "s1")

    assert result.exit_code == 0, result.output
    assert set(summary) == {"s1"}


def test_bonsai_v3_documents_are_rejected(monkeypatch, tmp_path):
    doc = {"sample_id": "s1", "typing_result": [{"analysis_type": "lineage"}]}

    result, _, _ = _compare(monkeypatch, tmp_path, _run_tree(tmp_path), [doc])

    assert result.exit_code == 1


@pytest.mark.parametrize("db_version, expected", [
    ({"name": "tbdb", "commit": "abc"}, "tbdb abc"),
    ({"name": "tbdb", "Date": "2024-05-08 16:25:28.388882"}, "tbdb tbdb_2024-05-08"),
    ({"name": "tbdb", "Date": "Wed May 08 16:25:28 2024 +0200"}, "tbdb tbdb_2024-05-08"),
])
def test_tbdb_version_matches_bonsai_prp(db_version, expected):
    assert _tbdb_version(db_version) == expected
