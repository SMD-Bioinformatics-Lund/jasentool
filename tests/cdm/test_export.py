"""Tests for to_cdm_format."""

from jasentool.cdm.export import to_cdm_format
from jasentool.cdm.models.qc import GambitcoreQcResult, PostAlignQcResult, QuastQcResult
from jasentool.cdm.models.typing import TypingResultCgMlst
from jasentool.cdm.types import (
    FullAnalysisResult,
    ParsedSampleResults,
    PipelineDefinition,
    PipelineInfo,
    PipelineRun,
    PipelineRunConfig,
    SequencingInfo,
)


def _sample_result(analysis_results):
    return ParsedSampleResults(
        sample_id="s1",
        sample_name="s1",
        lims_id="l1",
        sequencing=SequencingInfo(sequencing_run_id="r1", platform="illumina"),
        pipeline=PipelineRun(
            pipeline_run_id="r1",
            assay="test",
            executed_at="2024-01-01T00:00:00",
            pipeline_info=PipelineInfo(
                definition=PipelineDefinition(
                    name="jasen", version="1.0", release_life_cycle="production"
                ),
                run_config=PipelineRunConfig(command="nextflow run"),
                artifacts=[],
            ),
        ),
        analysis_results=analysis_results,
    )


def test_to_cdm_format_includes_expected_records():
    results = [
        FullAnalysisResult(
            software="postalignqc",
            software_version="1.0",
            parser_name="SamtoolsQcParser",
            parser_version=1,
            parser_status="parsed",
            analysis_type="qc",
            results=PostAlignQcResult(n_reads=100, n_read_pairs=50),
        ),
        FullAnalysisResult(
            software="quast",
            software_version="5.0",
            parser_name="QuastParser",
            parser_version=1,
            parser_status="parsed",
            analysis_type="qc",
            results=QuastQcResult(
                total_length=123, largest_contig=123, n_contigs=1, n50=123, assembly_gc=50.0
            ),
        ),
        FullAnalysisResult(
            software="gambitcore",
            software_version="1.0",
            parser_name="GambitCoreParser",
            parser_version=1,
            parser_status="parsed",
            analysis_type="species_prediction",
            results=GambitcoreQcResult(
                scientific_name="Staphylococcus aureus",
                completeness=99.0,
                assembly_core=1,
                species_core=1,
                closest_accession="ACC1",
                closest_distance=0.1,
                assembly_kmers=1,
                species_kmers_mean=1,
                species_kmers_std_dev=1,
                assembly_qc="green",
            ),
        ),
        FullAnalysisResult(
            software="chewbbaca",
            software_version="3.0",
            parser_name="ChewbbacaParser",
            parser_version=1,
            parser_status="parsed",
            analysis_type="cgmlst",
            results=TypingResultCgMlst(n_missing=5, alleles={}),
        ),
    ]
    cdm = to_cdm_format(_sample_result(results))

    ids = {r.id for r in cdm}
    assert ids == {"postalignqc", "quast", "gambitcore", "chewbbaca_missing_loci"}

    chewbbaca_record = next(r for r in cdm if r.id == "chewbbaca_missing_loci")
    assert chewbbaca_record.result == {"n_missing": 5}


def test_to_cdm_format_skips_unparsed_results():
    results = [
        FullAnalysisResult(
            software="quast",
            software_version="5.0",
            parser_name="QuastParser",
            parser_version=1,
            parser_status="error",
            reason="broken file",
            analysis_type="qc",
            results=None,
        ),
    ]
    cdm = to_cdm_format(_sample_result(results))
    assert cdm == []


def test_to_cdm_format_ignores_software_outside_target_list():
    results = [
        FullAnalysisResult(
            software="mlst",
            software_version="1.0",
            parser_name="MlstParser",
            parser_version=1,
            parser_status="parsed",
            analysis_type="mlst",
            results=None,
        ),
    ]
    cdm = to_cdm_format(_sample_result(results))
    assert cdm == []
