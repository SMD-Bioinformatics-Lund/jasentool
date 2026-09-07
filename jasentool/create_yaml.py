"""Module for creating YAML input files for Bonsai upload"""
import gzip
import yaml
from jasentool.log import get_logger

logger = get_logger(__name__)


def _accession_from_fasta(path):
    """Return a FASTA's first sequence accession (first header token), or None.

    The BAM/VCF the pipeline produces are aligned against this FASTA, so its
    first contig accession is the reference_genome_id IGV needs.
    """
    try:
        opener = gzip.open if str(path).endswith(".gz") else open
        with opener(path, "rt", encoding="utf-8") as fin:
            first_line = fin.readline()
    except OSError as exc:
        logger.warning("Could not read reference FASTA %s for accession: %s", path, exc)
        return None
    if not first_line.startswith(">"):
        logger.warning("Reference FASTA %s has no header line; cannot derive accession", path)
        return None
    tokens = first_line[1:].split()
    return tokens[0] if tokens else None

_ANALYSIS_TOOLS = [
    ("amrfinder", "amrfinder", None),
    ("chewbbaca", "chewbbaca", None),
    ("emmtyper", "emmtyper", None),
    ("gambitcore", "gambitcore", None),
    ("kleborate", "kleborate", None),
    ("kleborate_hamronization", "kleborate", "hamronization"),
    ("kraken", "kraken", None),
    ("mlst", "mlst", None),
    ("mykrobe", "mykrobe", None),
    ("nanoplot", "nanoplot", None),
    ("plasmidfinder", "plasmidfinder", None),
    ("plasmidfinder_genome_hits", "plasmidfinder", "genome_hits"),
    ("plasmidfinder_plasmid_seqs", "plasmidfinder", "plasmid_seqs"),
    ("quast", "quast", None),
    ("resfinder", "resfinder", None),
    ("samtools", "samtools", "coverage"),
    ("samtools_bedcov", "samtools", "bedcov"),
    ("samtools_stats", "samtools", "stats"),
    ("sccmec", "sccmectyper", None),
    ("serotypefinder", "serotypefinder", None),
    ("shigapass", "shigapass", None),
    ("shigatyper", "shigatyper", None),
    ("spatyper", "spatyper", None),
    ("tbprofiler", "tbprofiler", None),
    ("virulencefinder", "virulencefinder", None),
]

_VERSION_KEY_MAP = {
    "amrfinder":   "amrfinderplus",
    "kraken":      "bracken",
    "sccmectyper": "sccmec",
    "tbprofiler":  "tb-profiler",
}

class CreateYaml:
    @staticmethod
    def _igv_annotation(name, annot_type, uri, index_uri=None):
        entry = {"name": name, "type": annot_type, "uri": uri}
        if index_uri:
            entry["index_uri"] = index_uri
        return entry

    @staticmethod
    def _load_versions(path):
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        versions = {}
        for process_data in data.values():
            if isinstance(process_data, dict):
                for software, info in process_data.items():
                    if isinstance(info, dict) and "version" in info:
                        versions[software] = str(info["version"])
        return versions

    def run(self, options):
        prp_input = {}
        prp_input["sample_id"] = options.sample_id
        prp_input["sample_name"] = options.sample_name
        if options.lims_id:
            prp_input["lims_id"] = options.lims_id
        prp_input["groups"] = list(options.groups)
        if options.software_info:
            prp_input["software_info"] = list(options.software_info)

        reference_genome_id = getattr(options, "reference_genome_id", None)
        if not reference_genome_id and getattr(options, "ref_genome_sequence", None):
            reference_genome_id = _accession_from_fasta(options.ref_genome_sequence)
        if reference_genome_id:
            prp_input["reference_genome_id"] = reference_genome_id

        for field in ["nextflow_run_info", "ref_genome_sequence", "ref_genome_annotation"]:
            value = getattr(options, field, None)
            if value:
                prp_input[field] = value

        prp_input["igv_annotations"] = []
        prp_input["analysis_result"] = []

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

        versions = self._load_versions(options.versions) if options.versions else {}
        seen_software = set()

        for field, software, subcommand in _ANALYSIS_TOOLS:
            uri = getattr(options, field, None)
            if uri:
                entry = {"software": software}
                if subcommand:
                    entry["subcommand"] = subcommand
                if versions:
                    version_key = _VERSION_KEY_MAP.get(software, software)
                    version = versions.get(version_key)
                    if version:
                        entry["software_version"] = version
                    elif software not in seen_software:
                        print(f"WARNING: no version found for software '{software}'")
                    seen_software.add(software)
                entry["uri"] = uri
                prp_input["analysis_result"].append(entry)

        index_artifacts = {}
        for field in ["sourmash_signature", "ska_index"]:
            value = getattr(options, field, None)
            if value:
                index_artifacts[field] = value
        if index_artifacts:
            prp_input["index_artifacts"] = index_artifacts

        with open(options.output, 'w', encoding="utf-8") as fout:
            yaml.dump(prp_input, fout, default_flow_style=False, sort_keys=False)
        logger.info("YAML written to %s", options.output)
