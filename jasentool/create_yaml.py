"""Module for creating YAML input files for Bonsai upload"""
import json

import yaml
from jasentool.config import DATABASE_VERSIONS_FALLBACK, DATABASES_BY_SOFTWARE
from jasentool.log import get_logger

logger = get_logger(__name__)


_ANALYSIS_TOOLS = [
    ("amrfinder", "amrfinder", None),
    ("chewbbaca", "chewbbaca", None),
    ("emmtyper", "emmtyper", None),
    ("gambitcore", "gambitcore", None),
    ("kleborate", "kleborate", None),
    ("kleborate_hamronization", "kleborate", "hamronization"),
    ("kraken", "bracken", None),
    ("mlst", "mlst", None),
    ("mykrobe", "mykrobe", None),
    ("nanoplot", "nanoplot", None),
    ("plasmidfinder", "plasmidfinder", None),
    ("postalignqc", "postalignqc", None),
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

    @staticmethod
    def _load_database_meta(paths):
        """Read JASEN *_meta.json files into {database name: version}."""
        versions = {}
        for path in paths or []:
            try:
                with open(path, encoding="utf-8") as fin:
                    content = json.load(fin)
            except (OSError, json.JSONDecodeError) as exc:
                logger.warning("Skipping unreadable database info file %s: %s", path, exc)
                continue
            for record in content if isinstance(content, list) else [content]:
                if isinstance(record, dict) and record.get("name"):
                    versions[record["name"]] = str(record.get("version") or "").strip()
        return versions

    @staticmethod
    def _jasen_release(options):
        """JASEN release from --jasen-version, else the version recorded in the run info."""
        release = getattr(options, "jasen_version", None)
        run_info = getattr(options, "nextflow_run_info", None)
        if not release and run_info:
            try:
                with open(run_info, encoding="utf-8") as fin:
                    release = json.load(fin).get("version")
            except (OSError, json.JSONDecodeError, AttributeError):
                release = None
        return str(release).lstrip("v") if release else None

    def _database_info(self, options):
        """Database versions for the manifest's tools, from meta files or the release fallback."""
        meta = self._load_database_meta(getattr(options, "database_info", None))
        fallback = DATABASE_VERSIONS_FALLBACK.get(self._jasen_release(options), {})
        present = {
            software for field, software, _ in _ANALYSIS_TOOLS if getattr(options, field, None)
        }
        entries = []
        for software, names in DATABASES_BY_SOFTWARE.items():
            if software not in present:
                continue
            for name in names:
                version = meta.get(name)
                if not version or version == "unknown":
                    version = fallback.get(name)
                if version:
                    entries.append({
                        "software": software,
                        "database": name,
                        "database_version": version,
                    })
                else:
                    logger.warning("No version found for %s database '%s'", software, name)
        return entries

    def run(self, options):
        prp_input = {}
        prp_input["sample_id"] = options.sample_id
        prp_input["sample_name"] = options.sample_name
        if options.lims_id:
            prp_input["lims_id"] = options.lims_id
        prp_input["groups"] = list(options.groups)
        database_info = self._database_info(options)
        if database_info:
            prp_input["database_info"] = database_info

        reference_genome_accession = getattr(
            options, "reference_genome_accession", None
        )
        if reference_genome_accession:
            prp_input["reference_genome_accession"] = reference_genome_accession

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
