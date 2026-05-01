"""Module for creating YAML input files for Bonsai upload"""
import yaml
from jasentool.log import get_logger

logger = get_logger(__name__)

class CreateYaml:
    @staticmethod
    def _igv_annotation(name, annot_type, uri, index_uri=None):
        entry = {"name": name, "type": annot_type, "uri": uri}
        if index_uri:
            entry["index_uri"] = index_uri
        return entry

    def run(self, options):
        prp_input = {"igv_annotations": []}
        for field in [
            "amrfinder", "chewbbaca", "emmtyper", "gambitcore", "kleborate",
            "kleborate_hamronization", "kraken", "lims_id", "mlst", "mykrobe",
            "nanoplot", "nextflow_run_info", "plasmidfinder", "quast",
            "ref_genome_annotation", "ref_genome_sequence", "resfinder",
            "samtools", "samtools_bedcov", "samtools_stats", "sccmec",
            "serotypefinder", "shigapass", "ska_index",
            "sourmash_signature", "spatyper", "tbprofiler", "virulencefinder",
        ]:
            value = getattr(options, field, None)
            if value:
                prp_input[field] = value
        prp_input["sample_id"] = options.sample_id
        prp_input["sample_name"] = options.sample_name
        prp_input["groups"] = list(options.groups)
        if options.software_info:
            prp_input["software_info"] = list(options.software_info)
        if options.bam and options.bai:
            prp_input["igv_annotations"].append(
                self._igv_annotation("Read coverage", "alignment", options.bam, options.bai)
            )
        if options.tb_grading_rules_bed:
            prp_input["igv_annotations"].append(
                self._igv_annotation("tbdb grading rules bed", "bed", options.tb_grading_rules_bed)
            )
        if options.tbdb_bed:
            prp_input["igv_annotations"].append(
                self._igv_annotation("tbdb bed", "bed", options.tbdb_bed)
            )
        if options.vcf:
            prp_input["igv_annotations"].append(
                self._igv_annotation("Predicted variants", "variant", options.vcf)
            )
        with open(options.output, 'w', encoding="utf-8") as fout:
            yaml.dump(prp_input, fout, default_flow_style=False)
        logger.info("YAML written to %s", options.output)
