"""Module for building CDM input files from a JASEN sample manifest."""

import json

from pydantic import ValidationError

from jasentool.cdm.export import to_cdm_format
from jasentool.cdm.io_manifest import read_manifest
from jasentool.cdm.loader import parse_manifest_for_analysis
from jasentool.log import get_logger

logger = get_logger(__name__)


class FormatCdm:
    """Build a CDM input file from a sample manifest."""

    def run(self, options):
        manifest = read_manifest(options.manifest)
        try:
            results_obj = parse_manifest_for_analysis(manifest)
        except ValidationError as err:
            logger.error("Generated result failed validation: %s", err)
            raise

        cdm_result = to_cdm_format(results_obj)
        serialized = [e.model_dump(mode="json") for e in cdm_result]
        blob = json.dumps(serialized, indent=3)
        if options.output_file is None:
            print(blob)
        else:
            with open(options.output_file, "w", encoding="utf-8") as fout:
                fout.write(blob)
        logger.info("Finished generating CDM input")
