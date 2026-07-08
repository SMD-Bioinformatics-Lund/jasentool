"""Functions for building CDM input records from parsed pipeline results."""

import logging

from jasentool.cdm.models.enums import AnalysisSoftware

from .types import CdmRecord, CdmRecords, ParsedSampleResults

LOG = logging.getLogger(__name__)


def to_cdm_format(sample_results: ParsedSampleResults) -> CdmRecords:
    """Format a sample result into the output expected by CDM."""
    # list of generic parsing
    targets = ["postalignqc", "quast", "gambitcore"]
    results: list[CdmRecord] = []
    for res in sample_results.analysis_results:
        if res.software not in targets:
            continue
        if res.parser_status != "parsed":
            LOG.warning(res.reason)
            continue
        results.append(
            CdmRecord(
                id=str(res.software),
                software=res.software,
                result=res.results.model_dump(),
            )
        )

    # specific rules for chewbbaca
    for res in sample_results.analysis_results:
        if res.software != AnalysisSoftware.CHEWBBACA:
            continue

        if res.parser_status != "parsed":
            LOG.warning(res.reason)
            continue

        results.append(
            CdmRecord(
                id="chewbbaca_missing_loci",
                software=res.software,
                result={"n_missing": res.results.n_missing},
            )
        )
    return results
