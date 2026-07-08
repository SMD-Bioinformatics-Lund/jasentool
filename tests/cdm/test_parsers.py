"""Tests for the CDM-relevant parsers (postalignqc, quast, gambitcore, chewbbaca)."""

from pathlib import Path

import jasentool.cdm  # noqa: F401  (triggers parser auto-registration)
from jasentool.cdm.core.registry import run_parser

FIXTURES = Path(__file__).parent.parent / "fixtures" / "cdm"


def test_samtools_qc_parser():
    ev = run_parser(
        software="samtools",
        subcommand="stats",
        version="1.17",
        data=str(FIXTURES / "samtools_stats.txt"),
        bedcov_path=str(FIXTURES / "samtools_bedcov.txt"),
    )
    assert ev.software == "postalignqc"
    (result,) = ev.results.values()
    assert result.status == "parsed"
    assert result.value.n_reads > 0
    assert result.value.mean_cov is not None


def test_quast_parser():
    ev = run_parser(software="quast", version="5.0", data=str(FIXTURES / "quast.tsv"))
    (result,) = ev.results.values()
    assert result.status == "parsed"
    assert result.value.total_length > 0


def test_gambitcore_parser():
    ev = run_parser(software="gambitcore", version="1.0", data=str(FIXTURES / "gambitcore.tsv"))
    (result,) = ev.results.values()
    assert result.status == "parsed"
    assert result.value.scientific_name == "Staphylococcus aureus"


def test_chewbbaca_parser():
    ev = run_parser(software="chewbbaca", version="3.0", data=str(FIXTURES / "chewbbaca.out"))
    (result,) = ev.results.values()
    assert result.status == "parsed"
    assert result.value.n_missing >= 0
