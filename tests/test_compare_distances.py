import random

import pytest
from click.testing import CliRunner

from jasentool.cli import cli
from jasentool.compare_distances import CompareDistances
from jasentool.matrix import Matrix

CALLS = ["1", "2", "3", "INF-2", "INF-7", "-", "LNF", "PLOT3", "NIPH", "ASM", "0"]


def _random_calls(n_samples, n_loci, seed):
    rng = random.Random(seed)
    return {f"s{i}": [rng.choice(CALLS) for _ in range(n_loci)] for i in range(n_samples)}


def _pairwise_reference(calls, sample_ids):
    return [[Matrix.compare_cgmlst_alleles(calls[a], calls[b]) for b in sample_ids]
            for a in sample_ids]


@pytest.mark.parametrize("threads", [1, 3])
def test_generate_matrix_matches_pairwise_reference(threads):
    calls = _random_calls(25, 40, seed=1)
    ids = list(calls)

    fast = Matrix.generate_matrix(ids, lambda s: calls[s], threads)

    assert fast.to_numpy().tolist() == _pairwise_reference(calls, ids)
    assert list(fast.index) == ids and list(fast.columns) == ids


def test_generate_matrix_leaves_samples_without_alleles_as_nan():
    calls = {"s1": ["1", "2"], "s2": ["1", "3"], "s3": []}

    matrix = Matrix.generate_matrix(list(calls), lambda s: calls[s])

    assert matrix.loc["s1", "s2"] == 1
    assert matrix.loc["s3"].isna().all() and matrix["s3"].isna().all()


def test_generate_matrix_rejects_unequal_allele_lists():
    calls = {"s1": ["1", "2", "3"], "s2": ["1", "4"]}

    with pytest.raises(ValueError, match="differ in length"):
        Matrix.generate_matrix(list(calls), lambda s: calls[s])


def test_dash_change_matches_locus_by_locus_count():
    calls1 = _random_calls(20, 30, seed=2)
    calls2 = _random_calls(20, 30, seed=3)
    ids = list(calls1)
    is_missing = CompareDistances._is_missing
    expected = [[0 if i == j else sum(
        (not is_missing(a1) and not is_missing(b1)) != (not is_missing(a2) and not is_missing(b2))
        for a1, b1, a2, b2 in zip(calls1[i], calls1[j], calls2[i], calls2[j])
    ) for j in ids] for i in ids]

    dash_change = CompareDistances._build_dash_change_matrix(calls1, calls2, ids)

    assert dash_change.to_numpy().tolist() == expected


def _write_tsv(path, rows):
    path.write_text("\n".join("\t".join(map(str, row)) for row in rows) + "\n")


@pytest.mark.parametrize("threads, expected_j", [(1, None), (4, "2"), (5, "2")])
def test_threads_split_across_both_cgmlst_dists_runs(monkeypatch, tmp_path, threads, expected_j):
    matrix_text = "cgmlst-dists\ts1\ts2\ns1\t0\t1\ns2\t1\t0\n"
    commands = []

    class FakeProc:
        stdout = matrix_text
        stderr = ""
        returncode = 0

    def fake_run(cmd, *args, **kwargs):
        commands.append(cmd)
        return FakeProc()

    monkeypatch.setattr("jasentool.compare_distances.subprocess.run", fake_run)
    rows = [["FILE", "loc1"], ["s1", 1], ["s2", 2]]
    f1, f2 = tmp_path / "file1.tsv", tmp_path / "file2.tsv"
    _write_tsv(f1, rows)
    _write_tsv(f2, rows)

    result = CliRunner().invoke(cli, [
        "compare-distances", "-i", str(f1), str(f2), "-o", str(tmp_path / "out"),
        "--threads", str(threads),
    ])

    assert result.exit_code == 0, result.output
    assert len(commands) == 2
    for cmd in commands:
        j = cmd[cmd.index("-j") + 1] if "-j" in cmd else None
        assert j == expected_j
