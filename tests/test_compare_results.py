import copy
import csv
import json
import shutil
from pathlib import Path

import pytest
from click.testing import CliRunner

from jasentool.cli import cli
from jasentool.compare_results import _mykrobe_variant, _tbdb_version
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


def _run_tree(tmp_path, sample_ids=("s1",), tbprofiler_edit=None, mykrobe=True):
    root = tmp_path / "run"
    tbp_dir = root / "mtuberculosis" / "tbprofiler_mergedb"
    myk_dir = root / "mtuberculosis" / "mykrobe"
    tbp_dir.mkdir(parents=True)
    myk_dir.mkdir(parents=True)
    for sample_id in sample_ids:
        data = json.loads((FIXTURES / "tbprofiler.json").read_text())
        if tbprofiler_edit:
            tbprofiler_edit(data)
        (tbp_dir / f"{sample_id}_tbprofiler.json").write_text(json.dumps(data))
        if mykrobe:
            shutil.copy(FIXTURES / "mykrobe.csv", myk_dir / f"{sample_id}_mykrobe.csv")
    return root


def _compare(monkeypatch, tmp_path, root, docs, *extra):
    monkeypatch.setattr(Database, "initialize", lambda *a, **kw: None)
    monkeypatch.setattr(Database, "find", FakeBonsai(docs).find)
    out = tmp_path / "out" / "compare.csv"
    result = runner.invoke(cli, ["compare-results", "--input-dir", str(root), "-o", str(out), *extra])
    summary = list(csv.DictReader(out.open())) if out.exists() else []
    diffs_path = out.with_name("compare_differences.csv")
    diffs = list(csv.DictReader(diffs_path.open())) if diffs_path.exists() else []
    return result, {(r["sample_id"], r["software"]): r for r in summary}, diffs


def test_run_parsed_like_bonsai_is_identical(monkeypatch, tmp_path):
    result, summary, diffs = _compare(monkeypatch, tmp_path, _run_tree(tmp_path), [BONSAI_DOC])

    assert result.exit_code == 0, result.output
    assert summary["s1", "tbprofiler"]["status"] == "identical"
    assert summary["s1", "tbprofiler"]["run_n_variants"] == "66"
    assert summary["s1", "tbprofiler"]["run_database"] == (
        "converged_who_fohm_tbdb converged_who_fohm_tbdb_2024-05-08")
    assert summary["s1", "mykrobe"]["status"] == "identical"
    assert summary["s1", "mykrobe"]["run_sublineage"] == "lineage2.2.4"
    assert diffs == []


def test_tbprofiler_differences_are_reported(monkeypatch, tmp_path):
    def edit(data):
        data["sub_lineage"] = "lineage2.2.2"
        data["dr_variants"][0]["gene_name"] = "renamed"
        data["other_variants"].pop(0)
        data["pipeline"]["db_version"] = {"name": "tbdb", "commit": "abc123"}

    result, summary, diffs = _compare(
        monkeypatch, tmp_path, _run_tree(tmp_path, tbprofiler_edit=edit), [BONSAI_DOC])

    assert result.exit_code == 0, result.output
    row = summary["s1", "tbprofiler"]
    assert row["status"] == "differs"
    assert (row["variants_only_in_bonsai"], row["variants_only_in_run"]) == ("1", "0")
    fields = {d["field"]: d for d in diffs if d["software"] == "tbprofiler"}
    assert set(fields) == {"sublineage", "n_variants", "variant", "variant_gene", "database"}
    assert fields["sublineage"]["run_value"] == "lineage2.2.2"
    assert fields["n_variants"]["bonsai_value"] == "66" and fields["n_variants"]["run_value"] == "65"
    assert fields["variant"]["bonsai_value"].startswith("gyrA:7362G>C")
    assert fields["variant_gene"]["run_value"].startswith("renamed:761104")
    assert fields["database"]["run_value"] == "tbdb abc123"
    assert summary["s1", "mykrobe"]["status"] == "identical"


def test_mykrobe_lineage_and_variant_differences(monkeypatch, tmp_path):
    doc = copy.deepcopy(BONSAI_DOC)
    mykrobe_lineage = next(e for e in doc["typing_result"] if e["software"] == "mykrobe")
    mykrobe_lineage["result"]["sublineage"] = "lineage2.2.1"
    mykrobe_amr = next(e for e in doc["element_type_result"] if e["software"] == "mykrobe")
    mykrobe_amr["result"]["variants"].pop()

    result, summary, diffs = _compare(monkeypatch, tmp_path, _run_tree(tmp_path), [doc])

    assert result.exit_code == 0, result.output
    assert summary["s1", "mykrobe"]["status"] == "differs"
    fields = [d["field"] for d in diffs if d["software"] == "mykrobe"]
    assert sorted(fields) == ["n_variants", "sublineage", "variant"]


def test_samples_and_tools_missing_on_one_side(monkeypatch, tmp_path):
    root = _run_tree(tmp_path, sample_ids=("s1", "s2"), mykrobe=False)

    result, summary, _ = _compare(monkeypatch, tmp_path, root, [BONSAI_DOC])

    assert result.exit_code == 0, result.output
    assert summary["s1", "mykrobe"]["status"] == "missing_in_run"
    assert summary["s2", "tbprofiler"]["status"] == "missing_in_bonsai"
    assert ("s2", "mykrobe") not in summary


def test_sample_id_filter(monkeypatch, tmp_path):
    root = _run_tree(tmp_path, sample_ids=("s1", "s2"))

    result, summary, _ = _compare(monkeypatch, tmp_path, root, [BONSAI_DOC], "--sample-id", "s1")

    assert result.exit_code == 0, result.output
    assert {sid for sid, _ in summary} == {"s1"}


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


def test_mykrobe_substitution_codons_are_reduced():
    variant = _mykrobe_variant("katG_S315T-GCT2155167GGT:0:2624:17362")

    assert (variant.gene, variant.pos, variant.ref, variant.alt) == ("katG", 2155167, "C", "G")
