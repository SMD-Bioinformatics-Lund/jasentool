"""Rebuild Bonsai manifest YAMLs (and their merged versions.yml) from the backup tree.

Reconstructs the input that `create-yaml` needs by locating each sample's
analysis-result files under `--backup-dir` using the same per-profile output
declarations (`jasentool.config`) that `check-backup` scans against, then
merging that sample's scattered per-process `_versions.yml` files (JASEN
writes one per process invocation) into a single versions file the way
`concatenate-files` would.
"""

import glob
import json
import os
import types

import yaml
from tqdm import tqdm

from jasentool.check_backup import _as_list, _glob_matches
from jasentool.config import CREATE_YAML_FIELD_MAP, CREATE_YAML_VCF_PRIORITY, get_profile
from jasentool.create_yaml import _ANALYSIS_TOOLS, _VERSION_KEY_MAP, CreateYaml
from jasentool.database import Database
from jasentool.log import get_logger

logger = get_logger(__name__)

# create-yaml reads these via getattr(); _REQUIRED_FIELDS it accesses directly,
# so those must exist on the options namespace even when unset.
_OPTIONAL_FIELDS = [field for field, _, _ in _ANALYSIS_TOOLS] + [
    "sourmash_signature", "ska_index",
    "nextflow_run_info", "ref_genome_sequence", "ref_genome_annotation",
]
_REQUIRED_FIELDS = ["bam", "bai", "tb_grading_rules_bed", "tbdb_bed", "vcf", "software_info"]

_FIELD_TO_VERSION_KEY = {
    field: _VERSION_KEY_MAP.get(software, software)
    for field, software, _ in _ANALYSIS_TOOLS
}
_FALLBACK_PROCESS_KEY = "jasentool_version_fallback"
_RUN_METADATA_SOFTWARE = "save_analysis_metadata"

# release_life_cycle values JASEN emits that bonsai-prp's schema doesn't accept.
_RELEASE_LIFE_CYCLE_MAP = {"diagnostic": "production"}


def _load_versions_file(path):
    """Load one `_versions.yml`, dropping junk lines (a leaked `END_VERSIONS`
    terminator or a stray bare version) that would otherwise break YAML parsing.

    Returns the parsed object, or None if the file is unreadable, empty, or still
    unparseable (logged and skipped so one bad file can't abort the run).
    """
    try:
        with open(path, "r", encoding="utf-8") as fin:
            text = fin.read()
    except OSError as exc:
        logger.warning("Skipping unreadable versions file %s: %s", path, exc)
        return None
    cleaned = "\n".join(
        line for line in text.splitlines() if not line.strip() or ":" in line
    )
    try:
        return yaml.safe_load(cleaned)
    except yaml.YAMLError as exc:
        logger.warning("Skipping unparseable versions file %s: %s", path, exc)
        return None


class RebuildManifests:
    """Regenerate `<sample_id>_bonsai.yaml` manifests for every backed-up sample of a profile."""

    def __init__(self, options):
        self.options = options
        self.profile = options.profile
        self.backup_dir = options.backup_dir
        self.output_dir = options.output_dir
        self.versions_fallback = self._load_versions_fallback(
            getattr(options, "versions_fallback", None)
        )

    @staticmethod
    def _load_versions_fallback(path):
        """Load the flat `software: version` fallback file into a dict, or {} if none given."""
        if not path:
            return {}
        with open(path, "r", encoding="utf-8") as fin:
            data = yaml.safe_load(fin) or {}
        return {str(key): str(version) for key, version in data.items()}

    def _fetch_bonsai_samples(self):
        query = {"pipeline.analysis_profile": self.profile}
        if self.options.sample_id:
            query["sample_id"] = self.options.sample_id
        projection = {"_id": 0, "sample_id": 1, "sample_name": 1, "lims_id": 1}
        samples = Database.find(self.options.db_collection, query, projection)
        if self.options.sample_id and not samples:
            logger.error(
                "sample_id '%s' not found for profile '%s' in %s/%s",
                self.options.sample_id, self.profile,
                self.options.db_name, self.options.db_collection,
            )
        return samples

    def _discover_samples_from_tree(self, outputs, species):
        """Discover sample_ids by scanning the backup tree (used with `--no-bonsai`).

        A filename ending in a declared `<mask><file_ext>` suffix contributes its
        stripped prefix as a sample_id, unioned across all outputs. Wildcard-mask
        outputs and `_versions.yml` files are skipped. sample_name/lims_id are left
        unset here; the run metadata JSON supplies them later if present.
        """
        sample_ids = set()
        for output in outputs:
            mask = output.get("mask", "")
            if "*" in mask:
                continue
            search_dir = os.path.join(self.backup_dir, species, output["dirname"])
            if not os.path.isdir(search_dir):
                continue
            names = os.listdir(search_dir)
            for ext in _as_list(output["file_ext"]):
                suffix = f"{mask}{ext}"
                for name in names:
                    if name.endswith("_versions.yml"):
                        continue
                    if name.endswith(suffix) and len(name) > len(suffix):
                        sample_ids.add(name[: -len(suffix)])
        if self.options.sample_id:
            sample_ids = {sid for sid in sample_ids if sid == self.options.sample_id}
            if not sample_ids:
                logger.error(
                    "sample_id '%s' not found under %s for profile '%s'",
                    self.options.sample_id, self.backup_dir, self.profile,
                )
        return [
            {"sample_id": sid, "sample_name": None, "lims_id": None}
            for sid in sorted(sample_ids)
        ]

    def _fetch_groups(self, sample_ids):
        """Return {sample_id: [group_name, ...]} via reverse lookup of sample_group.included_samples."""
        wanted = set(sample_ids)
        groups_by_sample = {sid: [] for sid in wanted}
        group_docs = Database.find(
            self.options.db_collection_groups, {}, {"_id": 0, "name": 1, "included_samples": 1},
        )
        for group in group_docs:
            name = group.get("name", "")
            for sid in (group.get("included_samples") or []):
                if sid in wanted:
                    groups_by_sample[sid].append(name)
        return groups_by_sample

    def _resolve_output_path(self, output, species, sample_id):
        """Return the first matching backup-tree path for `output`, or None."""
        dirname = output["dirname"]
        mask = output.get("mask", "")
        search_dir = os.path.join(self.backup_dir, species, dirname)
        for ext in _as_list(output["file_ext"]):
            matches = _glob_matches(search_dir, sample_id, mask, ext)
            if matches:
                return matches[0]
        return None

    def _resolve_run_metadata(self, outputs, species, sample_id):
        """Return (path, parsed_dict) for the sample's run metadata, or (None, {}).

        Writes a normalized copy into the output dir (translating any
        release_life_cycle value bonsai-prp rejects) and returns that copy's path,
        so the manifest's nextflow_run_info points at a valid, local file. The
        original in the backup tree is left untouched.
        """
        for output in outputs:
            if output["software_name"] != _RUN_METADATA_SOFTWARE:
                continue
            path = self._resolve_output_path(output, species, sample_id)
            if not path:
                return None, {}
            try:
                with open(path, "r", encoding="utf-8") as fin:
                    data = json.load(fin)
            except (OSError, json.JSONDecodeError) as exc:
                logger.warning("%s: could not read run metadata %s: %s", sample_id, path, exc)
                return None, {}
            life_cycle = data.get("release_life_cycle")
            if life_cycle in _RELEASE_LIFE_CYCLE_MAP:
                data["release_life_cycle"] = _RELEASE_LIFE_CYCLE_MAP[life_cycle]
            dest = os.path.abspath(os.path.join(self.output_dir, f"{sample_id}_analysis_meta.json"))
            with open(dest, "w", encoding="utf-8") as fout:
                json.dump(data, fout, indent=2)
            return dest, data
        return None, {}

    def _merge_versions(self, species, sample_id, needed_keys):
        """Merge the sample's per-process `_versions.yml` files into one file.

        Any `needed_keys` still missing after the merge are filled from the
        `--versions-fallback` map. Returns the written path, or None if neither
        the tree nor the fallback produced a version.
        """
        pattern = os.path.join(self.backup_dir, species, "*", f"{sample_id}_*_versions.yml")
        version_files = sorted(glob.glob(pattern))
        merged = {}
        for version_file in sorted(version_files):
            data = _load_versions_file(version_file)
            if data:
                merged.update(data)
        self._apply_versions_fallback(merged, sample_id, needed_keys)
        if not merged:
            return None
        dest = os.path.join(self.output_dir, f"{sample_id}_versions.yml")
        with open(dest, "w", encoding="utf-8") as fout:
            yaml.dump(merged, fout, default_flow_style=False)
        return dest

    def _apply_versions_fallback(self, merged, sample_id, needed_keys):
        """Fill any `needed_keys` absent from `merged` (tree) from the fallback map, in place."""
        if not self.versions_fallback:
            return
        present = {
            software
            for process_data in merged.values() if isinstance(process_data, dict)
            for software in process_data
        }
        filled = {
            key: self.versions_fallback[key]
            for key in needed_keys
            if key not in present and key in self.versions_fallback
        }
        if not filled:
            return
        merged[_FALLBACK_PROCESS_KEY] = {
            software: {"version": version} for software, version in filled.items()
        }
        logger.info(
            "%s: filled %d version(s) from fallback: %s", sample_id, len(filled),
            ", ".join(f"{k}={v}" for k, v in sorted(filled.items())),
        )

    def _resolve_fields(self, outputs, species, sample_id):
        """Return {create-yaml field: path} for every output found in the backup tree."""
        fields = {}
        vcf_candidates = {}
        for output in outputs:
            software_name = output["software_name"]
            if software_name not in CREATE_YAML_FIELD_MAP and software_name not in CREATE_YAML_VCF_PRIORITY:
                continue
            path = self._resolve_output_path(output, species, sample_id)
            if not path:
                continue
            if software_name in CREATE_YAML_VCF_PRIORITY:
                vcf_candidates[software_name] = path
            else:
                fields[CREATE_YAML_FIELD_MAP[software_name]] = path
        for candidate in CREATE_YAML_VCF_PRIORITY:
            if candidate in vcf_candidates:
                fields["vcf"] = vcf_candidates[candidate]
                break
        return fields

    def _build_sample_yaml(self, doc, outputs, species, groups_by_sample):
        sample_id = doc["sample_id"]
        fields = self._resolve_fields(outputs, species, sample_id)
        needed_keys = {
            _FIELD_TO_VERSION_KEY[field]
            for field in fields if field in _FIELD_TO_VERSION_KEY
        }
        versions_path = self._merge_versions(species, sample_id, needed_keys)
        metadata_path, metadata = self._resolve_run_metadata(outputs, species, sample_id)

        create_yaml_options = types.SimpleNamespace(**{field: None for field in _OPTIONAL_FIELDS})
        for field in _REQUIRED_FIELDS:
            setattr(create_yaml_options, field, None)
        create_yaml_options.software_info = []
        for field, path in fields.items():
            setattr(create_yaml_options, field, path)

        create_yaml_options.sample_id = sample_id
        create_yaml_options.sample_name = (
            doc.get("sample_name") or metadata.get("sample_name") or sample_id
        )
        create_yaml_options.lims_id = doc.get("lims_id") or metadata.get("lims_id")
        create_yaml_options.nextflow_run_info = metadata_path
        create_yaml_options.groups = groups_by_sample.get(sample_id, [])
        create_yaml_options.versions = versions_path
        create_yaml_options.output = os.path.join(self.output_dir, f"{sample_id}_bonsai.yaml")

        CreateYaml().run(create_yaml_options)
        return bool(fields), versions_path is not None, metadata_path is not None

    def run(self):
        """Entry point: resolve profile, fetch samples, rebuild each manifest."""
        profile_entry = get_profile(self.profile)
        species = profile_entry["species"]
        outputs = profile_entry.get("outputs", []) or []

        if self.options.no_bonsai:
            samples = self._discover_samples_from_tree(outputs, species)
        else:
            Database.initialize(self.options.db_name, uri=self.options.address)
            samples = self._fetch_bonsai_samples()
        if not samples:
            logger.error("No samples found to rebuild")
            return

        os.makedirs(self.output_dir, exist_ok=True)
        sample_ids = [s["sample_id"] for s in samples if s.get("sample_id")]
        groups_by_sample = (
            {} if self.options.no_bonsai else self._fetch_groups(sample_ids)
        )

        n_written = 0
        n_no_fields = 0
        n_no_versions = 0
        n_no_metadata = 0
        progress = tqdm(
            samples, total=len(samples),
            desc=f"rebuild-manifests [{self.profile}]", unit="sample",
        )
        for doc in progress:
            sample_id = doc.get("sample_id")
            if not sample_id:
                logger.warning("Skipping doc with no sample_id: %s", doc)
                continue
            has_fields, has_versions, has_metadata = self._build_sample_yaml(
                doc, outputs, species, groups_by_sample,
            )
            n_written += 1
            if not has_fields:
                logger.warning("%s: no analysis-result files found under %s", sample_id, self.backup_dir)
                n_no_fields += 1
            if not has_versions:
                n_no_versions += 1
            if not has_metadata:
                logger.warning(
                    "%s: no analysis_meta.json found; manifest will lack nextflow_run_info "
                    "and lims_id (bonsai-prp requires both)", sample_id,
                )
                n_no_metadata += 1

        logger.info("%d manifests written to %s", n_written, self.output_dir)
        if n_no_fields:
            logger.warning("%d samples had no analysis-result files found", n_no_fields)
        if n_no_versions:
            logger.warning("%d samples had no per-process _versions.yml files found", n_no_versions)
        if n_no_metadata:
            logger.warning("%d samples had no analysis_meta.json (missing run info + lims_id)", n_no_metadata)
