"""Rebuild Bonsai manifest YAMLs (and their merged versions.yml) from the backup tree.

Reconstructs the input that `create-yaml` needs by locating each sample's
analysis-result files under `--backup-dir` using the same per-profile output
declarations (`jasentool.config`) that `check-backup` scans against, then
merging that sample's scattered per-process `_versions.yml` files (JASEN
writes one per process invocation) into a single versions file the way
`concatenate-files` would.
"""

import glob
import os
import types

import yaml
from tqdm import tqdm

from jasentool.check_backup import _as_list, _glob_matches
from jasentool.config import CREATE_YAML_FIELD_MAP, CREATE_YAML_VCF_PRIORITY, get_profile
from jasentool.create_yaml import _ANALYSIS_TOOLS, CreateYaml
from jasentool.database import Database
from jasentool.log import get_logger

logger = get_logger(__name__)

# Attributes CreateYaml.run() only ever reads via getattr(..., None) -- safe
# to leave unset for anything the backup tree doesn't provide.
_OPTIONAL_FIELDS = [field for field, _, _ in _ANALYSIS_TOOLS] + [
    "sourmash_signature", "ska_index",
    "nextflow_run_info", "ref_genome_sequence", "ref_genome_annotation",
]

# Attributes CreateYaml.run() accesses directly (`options.x`) -- must always
# exist on the options namespace or it raises AttributeError.
_REQUIRED_FIELDS = ["bam", "bai", "tb_grading_rules_bed", "tbdb_bed", "vcf", "software_info"]

# Bash heredoc terminator JASEN uses to write versions.yml (`cat <<-END_VERSIONS`).
# The `<<-` form strips leading tabs only, so a space-indented closing delimiter
# isn't recognised and the literal sentinel leaks into the file, breaking YAML.
_HEREDOC_SENTINEL = "END_VERSIONS"


def _load_versions_file(path):
    """Load one `_versions.yml`, tolerating a leaked `END_VERSIONS` heredoc terminator.

    Drops any line that is exactly the sentinel (never valid versions.yml content)
    before parsing. Returns the parsed object, or None if the file is unreadable,
    still unparseable after cleaning, or empty -- each case logged and skipped so
    one bad file never aborts the whole rebuild.
    """
    try:
        with open(path, "r", encoding="utf-8") as fin:
            text = fin.read()
    except OSError as exc:
        logger.warning("Skipping unreadable versions file %s: %s", path, exc)
        return None
    cleaned = "\n".join(
        line for line in text.splitlines() if line.strip() != _HEREDOC_SENTINEL
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
        """Discover sample_ids straight from the backup tree, without consulting Bonsai.

        Used when `--no-bonsai` is set. Every filename under the profile's declared
        output dirs whose name ends in a known `<mask><file_ext>` suffix contributes
        its stripped prefix as a sample_id (union across all outputs, so a sample is
        found as long as at least one of its files is present). Stripping a known
        suffix is safe even for sample_ids that contain underscores. Wildcard-mask
        outputs are skipped (their prefix can't be recovered unambiguously) and
        per-process `_versions.yml` files are ignored. Bonsai-only metadata isn't
        available here: `sample_name` falls back to `sample_id`, `lims_id` is unset.
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
            {"sample_id": sid, "sample_name": sid, "lims_id": None}
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

    def _merge_versions(self, species, sample_id):
        """Merge this sample's per-process `_versions.yml` files; return the merged path or None.

        Each file is loaded defensively: the `_versions.yml` files are JASEN
        pipeline outputs we don't control, so a single malformed one is logged
        and skipped rather than aborting the whole rebuild. Returns None if no
        version file was found or none parsed successfully.
        """
        pattern = os.path.join(self.backup_dir, species, "*", f"{sample_id}_*_versions.yml")
        version_files = sorted(glob.glob(pattern))
        if not version_files:
            return None
        merged = {}
        for version_file in version_files:
            data = _load_versions_file(version_file)
            if data:
                merged.update(data)
        if not merged:
            return None
        dest = os.path.join(self.output_dir, f"{sample_id}_versions.yml")
        with open(dest, "w", encoding="utf-8") as fout:
            yaml.dump(merged, fout, default_flow_style=False)
        return dest

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
        versions_path = self._merge_versions(species, sample_id)

        create_yaml_options = types.SimpleNamespace(**{field: None for field in _OPTIONAL_FIELDS})
        for field in _REQUIRED_FIELDS:
            setattr(create_yaml_options, field, None)
        create_yaml_options.software_info = []
        for field, path in fields.items():
            setattr(create_yaml_options, field, path)

        create_yaml_options.sample_id = sample_id
        create_yaml_options.sample_name = doc.get("sample_name", "")
        create_yaml_options.lims_id = doc.get("lims_id")
        create_yaml_options.groups = groups_by_sample.get(sample_id, [])
        create_yaml_options.versions = versions_path
        create_yaml_options.output = os.path.join(self.output_dir, f"{sample_id}_bonsai.yaml")

        CreateYaml().run(create_yaml_options)
        return bool(fields), versions_path is not None

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
        progress = tqdm(
            samples, total=len(samples),
            desc=f"rebuild-manifests [{self.profile}]", unit="sample",
        )
        for doc in progress:
            sample_id = doc.get("sample_id")
            if not sample_id:
                logger.warning("Skipping doc with no sample_id: %s", doc)
                continue
            has_fields, has_versions = self._build_sample_yaml(doc, outputs, species, groups_by_sample)
            n_written += 1
            if not has_fields:
                logger.warning("%s: no analysis-result files found under %s", sample_id, self.backup_dir)
                n_no_fields += 1
            if not has_versions:
                n_no_versions += 1

        logger.info("%d manifests written to %s", n_written, self.output_dir)
        if n_no_fields:
            logger.warning("%d samples had no analysis-result files found", n_no_fields)
        if n_no_versions:
            logger.warning("%d samples had no per-process _versions.yml files found", n_no_versions)
