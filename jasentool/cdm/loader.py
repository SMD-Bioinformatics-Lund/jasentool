"""
Utilities for loading and normalizing pipeline results into the internal
canonical representation used to build CDM input records.

This module reads the outputs produced by a workflow execution (e.g. Nextflow),
including:

    • pipeline run metadata (command, version, config files)
    • sequencing metadata
    • sample-level manifest metadata (scalar + tabular)
    • analysis outputs parsed through the registered parsers

and converts them into structured Pydantic models that form the internal
representation of a processed sample.

This module does *not* perform validation, serialization, or API communication.
It acts purely as the ingestion and normalisation layer for pipeline outputs.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from jasentool.cdm.core.registry import get_parser, run_parser
from jasentool.cdm.exceptions import UnsupportedSoftwareError, UnsupportedVersionError
from jasentool.cdm.io.delimited import read_delimited
from jasentool.cdm.io.json import read_json

from .manifest import URI, AnalysisResult, IgvAnnotation, IndexArtifacts, SampleManifest
from .metadata import MetaEntry, TableMetadataEntry
from .types import (
    FullAnalysisResult,
    GenericMetadataRecord,
    InternalIndexArtifacts,
    InternalMetadataRecord,
    IgvAnnotationTrack,
    MinimalAnalysisRecord,
    ParsedSampleResults,
    PipelineArtifact,
    PipelineDefinition,
    PipelineInfo,
    PipelineRun,
    PipelineRunConfig,
    SequencingInfo,
    TabularMetadataRecord,
)

LOG = logging.getLogger(__name__)


def to_internal_run_info(
    *, run_info: dict[str, Any], analysis_results: list[AnalysisResult]
) -> PipelineRun:
    """Parse the run information dump from JASEN."""
    artifacts = [
        PipelineArtifact(
            software_name=a.software, software_version=a.software_version, uri=a.uri
        )
        for a in analysis_results
    ]

    # structure the data into its internal representation
    pipeline_def = PipelineDefinition(
        name=run_info.get("pipeline"),
        version=run_info.get("version") or run_info.get("commit"),
        commit=None if ((c := run_info.get("commit")) == "null") else c,
        release_life_cycle=run_info.get("release_life_cycle", "unknown"),
    )
    run_cnf = PipelineRunConfig(
        command=run_info.get("command"),
        analysis_profile=run_info.get("analysis_profile"),
        configuration_files=run_info.get("configuration_files", []),
    )
    return PipelineRun(
        pipeline_run_id=run_info.get("workflow_name"),
        assay=run_info.get("assay"),
        executed_at=run_info.get("date"),
        pipeline_info=PipelineInfo(
            definition=pipeline_def,
            run_config=run_cnf,
            artifacts=artifacts,
        ),
    )


def parse_date_from_run_id(run_id: str) -> datetime | None:
    """
    Get the date of sequencing from run id as datetime object.

    XXX_20240112 -> 2024-01-12
    """
    err_msg = "Unrecognized format of run_id, sequence time cant be determined"
    if "_" not in run_id:
        LOG.warning(err_msg)
        return None
    # parse date string
    try:
        seq_date = datetime.strptime(run_id.split("_")[0], r"%y%m%d")
    except ValueError:
        LOG.warning(err_msg)
        seq_date = None
    return seq_date


def to_internal_sequencing_info(run_info: dict[str, Any]) -> SequencingInfo:
    """Format sequencing info from pipeline metadata."""
    run_id = run_info.get("sequencing_run")
    return SequencingInfo(
        sequencing_run_id=run_id or "unknown",
        platform=run_info.get("sequencing_platform"),
        sequencing_method=run_info.get("sequencing_type"),
        sequenced_at=parse_date_from_run_id(run_id),
    )


def to_table_record(record: TableMetadataEntry) -> TabularMetadataRecord:
    """Format manifest table record as internal representation."""

    if not isinstance(record, TableMetadataEntry):
        raise ValueError("Function expects TableMetadataEntry got {type(record)}")

    suffix = Path(record.value).suffix
    if not Path(record.value).suffix in [".csv", ".tsv"]:
        raise ValueError(f"Dont know how to parse {suffix}")
    delimiter = "," if suffix == ".csv" else "\t"

    # read file
    reader = read_delimited(record.value, delimiter=delimiter)
    first_row = next(reader)
    cols = list(first_row)
    cells = [list(first_row.values())]

    # continue building the table
    for row in reader:
        cells.append(list(row.values()))
    return TabularMetadataRecord(
        fieldname=record.fieldname, columns=cols, cells=cells, category=record.category
    )


def to_generic_metadata_record(record: MetaEntry) -> GenericMetadataRecord:
    """Format metadata file as ."""
    return GenericMetadataRecord(
        fieldname=record.fieldname,
        value=record.value,
        category=record.category,
        data_type=record.type,
    )


def _path_if_file_uri(uri: URI | None) -> str | None:
    """Return the file path if the URI is a file URI and exists, else None."""
    if uri.scheme == "file":
        path = Path(uri.path)
        if path.exists():
            return path.as_posix()
    return None


def to_internal_artifacts(artifacts: IndexArtifacts) -> InternalIndexArtifacts:
    """Convert manifest index artifacts to internal representation."""

    return InternalIndexArtifacts(
        ska_index=_path_if_file_uri(artifacts.ska_index),
        sourmash_signature=_path_if_file_uri(artifacts.sourmash_signature),
    )


def _get_track_name(track: IgvAnnotation) -> str:
    """Get name if is defined otherwise use filename."""
    return track.name or Path(track.uri).name



def parse_base_results_from_manifest(manifest: SampleManifest) -> ParsedSampleResults:
    """Parse pipeline analysis results from a manifest file."""

    metadata: list[InternalMetadataRecord] = []
    for record in manifest.metadata:
        if record.type == "table":
            metadata.append(to_table_record(record))
        else:
            metadata.append(to_generic_metadata_record(record))

    raw_run_info = read_json(manifest.nextflow_run_info)

    annotations = [
        IgvAnnotationTrack(
            name=_get_track_name(a), type=a.type, uri=a.uri, index_uri=a.index_uri
        )
        for a in manifest.igv_annotations]

    return ParsedSampleResults(
        sample_id=manifest.sample_id,
        sample_name=manifest.sample_name,
        lims_id=manifest.lims_id,
        groups=manifest.groups,
        metadata=metadata,
        reference_genome_id=manifest.reference_genome_id,
        annotation_tracks=annotations,
        pipeline=to_internal_run_info(
            run_info=raw_run_info, analysis_results=manifest.analysis_result
        ),
        sequencing=to_internal_sequencing_info(run_info=raw_run_info),
        index_artifacts=(
            to_internal_artifacts(manifest.index_artifacts)
            if manifest.index_artifacts
            else None
        ),
    )


def parse_manifest_for_analysis(manifest: SampleManifest) -> ParsedSampleResults:
    """Parse the sample manifest and the analysis result files for internal use."""
    base_result = parse_base_results_from_manifest(manifest)

    # Build lookup: (software, subcommand) → file path
    available: dict[tuple[str, str | None], str] = {
        (r.software, r.subcommand): r.uri.path
        for r in manifest.analysis_result
    }

    # parse results from analysis softwares
    analysis_results: list[FullAnalysisResult] = []
    for res in manifest.analysis_result:
        if not res.uri.scheme == "file":
            raise NotImplementedError(
                f"No method for reading {res.uri.scheme} URI scheme."
            )

        # Skip entries with no registered parser (e.g. samtools bedcov, or any
        # software not needed to build CDM output)
        try:
            parser_cls = get_parser(
                res.software, version=res.software_version, subcommand=res.subcommand
            )
        except (UnsupportedSoftwareError, UnsupportedVersionError):
            continue

        # Pass bedcov path if available (used by samtools.stats for coverage metrics)
        kwargs: dict[str, str] = {}
        bedcov_path = available.get((res.software, "bedcov"))
        if bedcov_path is not None:
            kwargs["bedcov_path"] = bedcov_path

        ev = run_parser(
            software=res.software,
            subcommand=res.subcommand,
            version=res.software_version,
            data=res.uri.path,
            **kwargs,
        )
        for at, parser_result in ev.results.items():
            analysis_results.append(
                FullAnalysisResult(
                    software=ev.software,
                    software_version=ev.software_version,
                    parser_name=ev.parser_name,
                    parser_version=ev.parser_version,
                    parser_status=parser_result.status,
                    reason=parser_result.reason,
                    analysis_type=at,
                    results=parser_result.value,
                )
            )

    return base_result.model_copy(update={"analysis_results": analysis_results})
