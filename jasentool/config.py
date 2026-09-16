"""Per-profile expected outputs for the `check-backup` subcommand.

Each profile lists the JASEN process outputs that should appear in the backup
storage tree at `<backup-root>/<species>/<dirname>/<sample_id><mask><file_ext>`.

`<sample_id>` is the Bonsai doc's `sample_id` field. `mask` holds whatever
goes between `<sample_id>` and `<file_ext>` -- usually `_<software>` for the
canonical JASEN naming, sometimes empty (e.g. sourmash `<sample>.sig`) or a
literal `*` for cases where the suffix has historically varied.

Set `required=False` for outputs that are conditional on a feature flag
(`params.use_skesa`, `params.use_kraken`, ...) or platform (`nanopore` vs
`illumina` vs `iontorrent`). Missing required outputs flip a sample's status
to FAIL; missing non-required outputs are logged + tracked but do not.
"""


def _out(software_name, dirname, mask, file_ext, required=True):
    """Compact constructor for a per-output entry."""
    return {
        "software_name": software_name,
        "dirname": dirname,
        "mask": mask,
        "file_ext": file_ext,
        "required": required,
    }


# Outputs that run for every JASEN profile.
_COMMON_OUTPUTS = [
    _out("quast", "quast", "_quast", ".tsv"),
    _out("sourmash", "sourmash", "", ".sig"),
    _out("gambitcore", "gambitcore", "_gambitcore", ".tsv", required=False),
    _out("ska", "ska", "_ska_index", ".skf"),
    _out("create_yaml", "analysis_yaml", "_bonsai", ".yaml"),
    _out("format_jasen", "analysis_result", "_result", ".json"),
    _out("format_cdm", "cdm_input", "_qc_result", ".json"),
    _out("export_to_cdm", "qc", "", ".cdmpy"),
    _out("save_analysis_metadata", "analysis_metadata", "_analysis_meta", ".json"),
    _out("bracken", "kraken", "_bracken", ".out", required=False),
    # Optional / feature- and platform-gated entries — uncomment if/when needed.
    # The wildcard-mask entries (fastqc_*) trigger a full directory listing per
    # sample, which dominates runtime on NFS-backed backup trees; reinstate them
    # only alongside the (deferred) directory-listing cache in check_backup.py.
    # _out("fastqc_html", "fastqc", "_*", ".html", required=False),
    # _out("fastqc_zip", "fastqc", "_*", ".zip", required=False),
    # _out("nanoplot_html", "nanoplot", "_NanoPlot-report", ".html", required=False),
    # _out("nanoplot_txt", "nanoplot", "_NanoStats", ".txt", required=False),
    # _out("trimmomatic_R1", "trimmomatic", ".paired.trim_1", ".fastq.gz", required=False),
    # _out("trimmomatic_R2", "trimmomatic", ".paired.trim_2", ".fastq.gz", required=False),
    # _out("filtlong", "filtlong", "_filtered", ".fastq.gz", required=False),
    # _out("seqtk_sample", "seqtk_sample", "_seqtk", ".fastq.gz", required=False),
]

# Outputs that run for every profile EXCEPT mycobacterium_tuberculosis.
_NON_TB_OUTPUTS = [
    _out("amrfinderplus", "amrfinderplus", "_amrfinder", [".tsv", ".out"]),
    _out("resfinder_json", "resfinder", "_resfinder", ".json"),
    _out("resfinder_meta", "resfinder", "_resfinder_meta", ".json"),
    _out("resfinder_pheno_table", "resfinder", "_pheno_table", ".txt"),
    _out("resfinder_point_table", "resfinder", "_point_table", ".txt", required=False),
    _out("virulencefinder_json", "virulencefinder", "_virulencefinder", ".json"),
    _out("virulencefinder_meta", "virulencefinder", "_virulencefinder_meta", ".json"),
    # _out("plasmidfinder_json", "plasmidfinder", "_plasmidfinder", ".json"),
    # _out("plasmidfinder_meta", "plasmidfinder", "_plasmidfinder_meta", ".json"),
    # _out("plasmidfinder_genome_hits", "plasmidfinder",
    #      "_plasmidfinder_hit_in_genome_seq", ".fsa"),
    # _out("plasmidfinder_plasmid_seqs", "plasmidfinder",
    #      "_plasmidfinder_plasmid_seqs", ".fsa"),
    _out("chewbbaca", "chewbbaca", "_chewbbaca", [".tsv", ".out"]),
    _out("mlst_json", "mlst", "_mlst", ".json"),
    _out("mlst_novel", "mlst", "_mlst", ".novel", required=False),
    _out("freebayes", "vcf", "_freebayes", ".vcf"),
    # Optional / feature- and platform-gated entries — uncomment if/when needed.
    # Non-TB assembly variants (one will run depending on platform / feature flags)
    # _out("spades", "fasta", "_spades", ".fasta", required=False),
    # _out("skesa", "fasta", "_skesa", ".fasta", required=False),
    # _out("flye", "fasta", "_flye", ".fasta", required=False),
    # _out("medaka", "fasta", "_medaka", ".fasta", required=False),
    # Non-TB alignment / variant ancillaries (gated by platform / use_masking)
    _out("bwa_mem_ref", "bam", "_bwa", ".bam", required=False),
    _out("samtools_index_ref", "bam", "_bwa.bam", ".bai", required=False),
    # _out("clair3_ref", "vcf", "_clair3", ".vcf.gz", required=False),
    _out("mask_polymorph", "mask", "_mask", ".fasta"),
]

# Outputs that run only for mycobacterium_tuberculosis.
_TB_OUTPUTS = [
    _out("mykrobe", "mykrobe", "_mykrobe", ".csv"),
    _out("snippy_vcf", "snippy", "_snippy", ".vcf"),
    _out("tbprofiler_json", "tbprofiler_mergedb", "_tbprofiler", ".json"),
    _out("tbprofiler_vcf", "vcf", "_tbprofiler", ".vcf.gz"),
    _out("tbprofiler_bam", "bam", "_tbprofiler", ".bam"),
    _out("tbprofiler_bai", "bam", "_tbprofiler.bam", ".bai"),
    _out("annotate_delly", "vcf", "_annotated_delly", ".vcf"),
]

# Staphylococcus aureus-specific outputs.
_STAPH_OUTPUTS = [
    _out("sccmec", "sccmec", "_sccmec", ".tsv", required=False),
    _out("spatyper", "spatyper", "_spatyper", ".tsv", required=False),
]

# Escherichia coli-specific outputs.
_ECOLI_OUTPUTS = [
    # Optional / feature-gated entries — uncomment if/when needed.
    # _out("kleborate", "kleborate", "_kleborate", ".txt", required=False),
    # _out("kleborate_hamronization", "kleborate",
    #      "_kleborate_hAMRonization", ".txt", required=False),
    _out("serotypefinder_json", "serotypefinder", "_serotypefinder", ".json"),
    _out("serotypefinder_meta", "serotypefinder", "_serotypefinder_meta", ".json"),
    _out("shigatyper", "shigatyper", "", ".tsv"),
]

# Streptococcus pyogenes / streptococcus-specific outputs.
_STREP_OUTPUTS = [
    _out("emmtyper", "emmtyper", "_emmtyper", ".tsv"),
]

# Alignment QC outputs; run for non-Streptococcus profiles only.
_POST_ALIGN_QC = [
    _out("samtools_coverage", "coverage", "_*_mapcoverage", ".txt"),
    _out("samtools_stats", "samtools_stats", "", ".stats"),
    _out("samtools_bedcov", "samtools_bedcov", ".bedcov", ".tsv"),
    _out("post_align_qc", "postalignqc", "_qc", ".json", required=False),
]


# Maps an output's software_name to the create-yaml field it feeds, for
# rebuild-manifests. Outputs with no entry here are skipped.
CREATE_YAML_FIELD_MAP = {
    "quast": "quast",
    "sourmash": "sourmash_signature",
    "gambitcore": "gambitcore",
    "bracken": "kraken",
    "ska": "ska_index",
    "amrfinderplus": "amrfinder",
    "resfinder_json": "resfinder",
    "virulencefinder_json": "virulencefinder",
    "chewbbaca": "chewbbaca",
    "mlst_json": "mlst",
    "mykrobe": "mykrobe",
    "tbprofiler_json": "tbprofiler",
    "tbprofiler_bam": "bam",
    "tbprofiler_bai": "bai",
    "bwa_mem_ref": "bam",
    "samtools_index_ref": "bai",
    "sccmec": "sccmec",
    "spatyper": "spatyper",
    "serotypefinder_json": "serotypefinder",
    "shigatyper": "shigatyper",
    "emmtyper": "emmtyper",
    "samtools_coverage": "samtools",
    "samtools_stats": "samtools_stats",
    "samtools_bedcov": "samtools_bedcov",
    "post_align_qc": "postalignqc",
}

# Older runs wrote a single postalignqc JSON; newer ones write samtools stats.
# When a sample has both, keep only samtools.
CREATE_YAML_SUPERSEDED = {"postalignqc": "samtools_stats"}

# Outputs passed to create-yaml as --database-info, which takes a list.
CREATE_YAML_DATABASE_INFO = [
    "resfinder_meta",
    "virulencefinder_meta",
    "serotypefinder_meta",
]

# create-yaml has one IGV vcf slot; prefer these sources in order.
CREATE_YAML_VCF_PRIORITY = ["tbprofiler_vcf", "snippy_vcf", "freebayes"]

# create-yaml fields JASEN passes from params.symlink_dir rather than params.outdir.
CREATE_YAML_SYMLINKED_FIELDS = {"bam", "bai", "ska_index", "sourmash_signature", "vcf"}

# Tool versions pinned by each JASEN release's containers, for rebuild-manifests
# --jasen-version. Used only when the backup tree has no usable version for a tool the
# sample has an output for. Keys are the software name inside a versions.yml (what
# create-yaml looks up), not the container image name.
_JASEN_1_0_0 = {
    "amrfinderplus": "3.11.11",
    "blast": "2.14.0",
    "bracken": "2.8",
    "bwakit": "0.7.17.dev1",
    "chewbbaca": "3.3.2",
    "emmtyper": "0.2.0",
    "fastqc": "0.12.1",
    "flye": "2.9.3",
    "freebayes": "1.3.6",
    "hostile": "2.0.0",
    "htslib": "1.21",
    "kraken2": "2.1.2",
    "medaka": "2.0.1",
    "mlst": "2.23.0",
    "mykrobe": "0.12.2",
    "nanoplot": "1.43.0",
    "perl-json": "4.10",
    "quast": "5.2.0",
    "resfinder": "4.4.2",
    "samtools": "1.17",
    "sccmec": "1.2.0",
    "seqtk": "1.4",
    "serotypefinder": "2.0.2",
    "shigapass": "1.5.0",
    "ska2": "0.3.10",
    "skesa": "2.5.1",
    "snippy": "4.6.0",
    "sourmash": "4.8.2",
    "spades": "3.15.5",
    "spatyper": "0.3.3",
    "tb-profiler": "6.3.0",
    "virulencefinder": "2.0.4",
}

_JASEN_1_1_0 = {
    **_JASEN_1_0_0,
    "gambitcore": "0.0.2",
    "minimap2": "2.28",
    "postalignqc": "1.3.1",
    "prodigal": "2.6.3",
    "resfinder": "4.7.2",
}

_JASEN_1_1_2 = {
    **_JASEN_1_1_0,
    "postalignqc": "1.3.3",
}

_JASEN_1_2_0 = {
    **_JASEN_1_1_0,
    "chewbbaca": "3.4.0",
    "flye": "2.9.6",
    "kleborate": "3.2.4",
    "medaka": "2.2.0",
    "minimap2": "2.30",
    "nanoplot": "1.46.2",
    "postalignqc": "1.5.0",
    "virulencefinder": "3.2.0",
}

_JASEN_1_3_0 = {
    **_JASEN_1_2_0,
    "amrfinderplus": "4.2.7",
    "chewbbaca": "3.5.3",
    "clair3": "2.0.0",
    "filtlong": "0.3.1",
    "kraken2": "2.17.1",
    "postalignqc": "1.0.0",
}

VERSIONS_FALLBACK = {
    "1.0.0": _JASEN_1_0_0,
    "1.1.0": _JASEN_1_1_0,
    "1.1.1": _JASEN_1_1_0,
    "1.1.2": _JASEN_1_1_2,
    "1.2.0": _JASEN_1_2_0,
    "1.3.0": _JASEN_1_3_0,
}

# Databases each tool is run against, named as in the JASEN *_meta.json files.
DATABASES_BY_SOFTWARE = {
    "resfinder": ["resfinder", "pointfinder"],
    "virulencefinder": ["virulencefinder"],
    "serotypefinder": ["serotypefinder"],
    "plasmidfinder": ["plasmidfinder"],
    "tbprofiler": ["tbdb"],
}

# Database versions pinned in each JASEN release: submodule commits up to 1.1.2,
# Makefile versions from 1.2.0.
_JASEN_1_0_0_DATABASES = {
    "pointfinder": "cb424d459212782fb38a0d81a75fd089b7df704d",
    "resfinder": "8117fca4401e05529301b5cc95c192239a451f49",
    "serotypefinder": "ada62c62a7fa74032448bb2273d1f7045c59fdda",
    "tbdb": "4907915526b52ac2f20f1324613f5d4dc951e0bd",
    "virulencefinder": "041b8b30ede055f92cbd8eaf3679ca7554857514",
}

_JASEN_1_1_0_DATABASES = {
    "pointfinder": "694919f59a38980204009e7ade76bf319cb7df0b",
    "resfinder": "cf9bbc7b13f04de987f7dd4a3a1440c7af0b1ce0",
    "serotypefinder": "d9be114411a6561e8b5c43db292737c7275195f5",
    "tbdb": "4907915526b52ac2f20f1324613f5d4dc951e0bd",
    "virulencefinder": "9638945ea72ec748beded45bb9fe48351eee346f",
}

_JASEN_1_2_0_DATABASES = {
    "pointfinder": "4.1.1",
    "resfinder": "2.6.0",
    "serotypefinder": "1.1.0",
    "tbdb": "4907915526b52ac2f20f1324613f5d4dc951e0bd",
    "virulencefinder": "2.0.1",
}

DATABASE_VERSIONS_FALLBACK = {
    "1.0.0": _JASEN_1_0_0_DATABASES,
    "1.1.0": _JASEN_1_1_0_DATABASES,
    "1.1.1": _JASEN_1_1_0_DATABASES,
    "1.1.2": _JASEN_1_1_0_DATABASES,
    "1.2.0": _JASEN_1_2_0_DATABASES,
    "1.3.0": _JASEN_1_2_0_DATABASES,
}


def _build_outputs(*groups):
    out = []
    for group in groups:
        out.extend(group)
    return out


PROFILES = [
    {
        "profile": "staphylococcus_aureus",
        "species": "saureus",
        "species_full": "Staphylococcus aureus",
        "outputs": _build_outputs(
            _COMMON_OUTPUTS, _NON_TB_OUTPUTS, _STAPH_OUTPUTS, _POST_ALIGN_QC,
        ),
    },
    {
        "profile": "escherichia_coli",
        "species": "ecoli",
        "species_full": "Escherichia coli",
        "outputs": _build_outputs(
            _COMMON_OUTPUTS, _NON_TB_OUTPUTS, _ECOLI_OUTPUTS, _POST_ALIGN_QC,
        ),
    },
    {
        "profile": "mycobacterium_tuberculosis",
        "species": "mtuberculosis",
        "species_full": "Mycobacterium tuberculosis",
        "outputs": _build_outputs(_COMMON_OUTPUTS, _TB_OUTPUTS, _POST_ALIGN_QC),
    },
    {
        "profile": "streptococcus_pyogenes",
        "species": "spyogenes",
        "species_full": "Streptococcus pyogenes",
        "outputs": _build_outputs(_COMMON_OUTPUTS, _NON_TB_OUTPUTS, _STREP_OUTPUTS),
    },
    {
        "profile": "streptococcus",
        "species": "streptococcus",
        "species_full": "Streptococcus",
        "outputs": _build_outputs(_COMMON_OUTPUTS, _NON_TB_OUTPUTS, _STREP_OUTPUTS),
    },
]


def get_profile(name):
    """Return the profile dict matching `name`, or raise KeyError with the known list."""
    for profile in PROFILES:
        if profile["profile"] == name:
            return profile
    known = sorted(p["profile"] for p in PROFILES)
    raise KeyError(f"Profile '{name}' not found. Known profiles: {known}")
