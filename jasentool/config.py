"""Per-profile expected outputs for the `check-backup` subcommand.

Each profile lists the JASEN process outputs that should appear in the backup
storage tree at `<backup-root>/<species>/<dirname>/<sample_id><mask><file_ext>`.

`<sample_id>` is matched as either the Mongo `id` (sample_name) or the
alter-sample-id form (`<lims>_<seqrun>` lowercased). `mask` holds whatever
goes between `<sample_id>` and `<file_ext>` — usually `_<software>` for the
canonical JASEN naming, sometimes empty (e.g. sourmash `<sample>.sig`) or a
literal `*` for cases where the suffix has historically varied.

Set `required=False` for outputs that are conditional on a feature flag
(`params.use_skesa`, `params.use_kraken`, ...) or platform (`nanopore` vs
`illumina` vs `iontorrent`). Missing required outputs flip a sample's status
to FAIL; missing non-required outputs are logged + tracked but do not.
"""

# Outputs that run for every JASEN profile.
_COMMON_OUTPUTS = [
    {"software_name": "quast", "dirname": "quast", "mask": "_quast", "file_ext": ".tsv", "required": True},
    {"software_name": "sourmash", "dirname": "sourmash", "mask": "", "file_ext": ".sig", "required": True},
    {"software_name": "gambitcore", "dirname": "gambitcore", "mask": "_gambitcore", "file_ext": ".tsv", "required": True},
    {"software_name": "ska", "dirname": "ska", "mask": "_ska_index", "file_ext": ".skf", "required": True},
    {"software_name": "create_yaml", "dirname": "analysis_yaml", "mask": "", "file_ext": ".yaml", "required": True},
    {"software_name": "format_jasen", "dirname": "analysis_result", "mask": "_result", "file_ext": ".json", "required": True},
    {"software_name": "format_cdm", "dirname": "cdm_input", "mask": "_qc_result", "file_ext": ".json", "required": True},
    {"software_name": "export_to_cdm", "dirname": "qc", "mask": "", "file_ext": ".cdmpy", "required": True},
    {"software_name": "save_analysis_metadata", "dirname": "analysis_metadata", "mask": "_analysis_meta", "file_ext": ".json", "required": True},
    # Platform-gated short-read QC
    {"software_name": "fastqc_html", "dirname": "fastqc", "mask": "_*", "file_ext": ".html", "required": False},
    {"software_name": "fastqc_zip", "dirname": "fastqc", "mask": "_*", "file_ext": ".zip", "required": False},
    {"software_name": "nanoplot_html", "dirname": "nanoplot", "mask": "_NanoPlot-report", "file_ext": ".html", "required": False},
    {"software_name": "nanoplot_txt", "dirname": "nanoplot", "mask": "_NanoStats", "file_ext": ".txt", "required": False},
    # Optional QC/preprocessing
    {"software_name": "trimmomatic_R1", "dirname": "trimmomatic", "mask": ".paired.trim_1", "file_ext": ".fastq.gz", "required": False},
    {"software_name": "trimmomatic_R2", "dirname": "trimmomatic", "mask": ".paired.trim_2", "file_ext": ".fastq.gz", "required": False},
    {"software_name": "filtlong", "dirname": "filtlong", "mask": "_filtered", "file_ext": ".fastq.gz", "required": False},
    {"software_name": "seqtk_sample", "dirname": "seqtk_sample", "mask": "_seqtk", "file_ext": ".fastq.gz", "required": False},
]

# Outputs that run for every profile EXCEPT mycobacterium_tuberculosis.
_NON_TB_OUTPUTS = [
    {"software_name": "amrfinderplus", "dirname": "amrfinderplus", "mask": "_amrfinder", "file_ext": ".tsv", "required": True},
    {"software_name": "resfinder_json", "dirname": "resfinder", "mask": "_resfinder", "file_ext": ".json", "required": True},
    {"software_name": "resfinder_meta", "dirname": "resfinder", "mask": "_resfinder_meta", "file_ext": ".json", "required": True},
    {"software_name": "resfinder_pheno_table", "dirname": "resfinder", "mask": "_pheno_table", "file_ext": ".txt", "required": True},
    {"software_name": "resfinder_point_table", "dirname": "resfinder", "mask": "_point_table", "file_ext": ".txt", "required": False},
    {"software_name": "virulencefinder_json", "dirname": "virulencefinder", "mask": "_virulencefinder", "file_ext": ".json", "required": True},
    {"software_name": "virulencefinder_meta", "dirname": "virulencefinder", "mask": "_virulencefinder_meta", "file_ext": ".json", "required": True},
    {"software_name": "plasmidfinder_json", "dirname": "plasmidfinder", "mask": "_plasmidfinder", "file_ext": ".json", "required": True},
    {"software_name": "plasmidfinder_meta", "dirname": "plasmidfinder", "mask": "_plasmidfinder_meta", "file_ext": ".json", "required": True},
    {"software_name": "plasmidfinder_genome_hits", "dirname": "plasmidfinder", "mask": "_plasmidfinder_hit_in_genome_seq", "file_ext": ".fsa", "required": True},
    {"software_name": "plasmidfinder_plasmid_seqs", "dirname": "plasmidfinder", "mask": "_plasmidfinder_plasmid_seqs", "file_ext": ".fsa", "required": True},
    {"software_name": "chewbbaca", "dirname": "chewbbaca", "mask": "_chewbbaca", "file_ext": ".tsv", "required": True},
    {"software_name": "mlst_tsv", "dirname": "mlst", "mask": "_mlst", "file_ext": ".tsv", "required": True},
    {"software_name": "mlst_json", "dirname": "mlst", "mask": "_mlst", "file_ext": ".json", "required": True},
    {"software_name": "freebayes", "dirname": "vcf", "mask": "_freebayes", "file_ext": ".vcf", "required": True},
    # Non-TB assembly variants (one will run depending on platform / feature flags)
    {"software_name": "spades", "dirname": "fasta", "mask": "_spades", "file_ext": ".fasta", "required": False},
    {"software_name": "skesa", "dirname": "fasta", "mask": "_skesa", "file_ext": ".fasta", "required": False},
    {"software_name": "flye", "dirname": "fasta", "mask": "_flye", "file_ext": ".fasta", "required": False},
    {"software_name": "medaka", "dirname": "fasta", "mask": "_medaka", "file_ext": ".fasta", "required": False},
    # Non-TB alignment/variant ancillaries (gated by platform / use_masking)
    {"software_name": "bwa_mem_ref", "dirname": "bam", "mask": "_bwa", "file_ext": ".bam", "required": False},
    {"software_name": "clair3_ref", "dirname": "vcf", "mask": "_clair3", "file_ext": ".vcf.gz", "required": False},
    {"software_name": "mask_polymorph", "dirname": "mask", "mask": "_mask", "file_ext": ".fasta", "required": False},
]

# Outputs that run only for mycobacterium_tuberculosis.
_TB_OUTPUTS = [
    {"software_name": "mykrobe", "dirname": "mykrobe", "mask": "_mykrobe", "file_ext": ".csv", "required": True},
    {"software_name": "snippy_vcf", "dirname": "snippy", "mask": "_snippy", "file_ext": ".vcf", "required": True},
    {"software_name": "tbprofiler_json", "dirname": "tbprofiler_mergedb", "mask": "_tbprofiler", "file_ext": ".json", "required": True},
    {"software_name": "tbprofiler_vcf", "dirname": "vcf", "mask": "_tbprofiler", "file_ext": ".vcf.gz", "required": True},
    {"software_name": "tbprofiler_bam", "dirname": "bam", "mask": "_tbprofiler", "file_ext": ".bam", "required": True},
    {"software_name": "tbprofiler_bai", "dirname": "bam", "mask": "_tbprofiler.bam", "file_ext": ".bai", "required": True},
    {"software_name": "annotate_delly", "dirname": "vcf", "mask": "_annotated_delly", "file_ext": ".vcf", "required": True},
]

# Staphylococcus aureus-specific outputs.
_STAPH_OUTPUTS = [
    {"software_name": "sccmec", "dirname": "sccmec", "mask": "_sccmec", "file_ext": ".tsv", "required": True},
    {"software_name": "spatyper", "dirname": "spatyper", "mask": "_spatyper", "file_ext": ".tsv", "required": True},
]

# Escherichia coli-specific outputs.
_ECOLI_OUTPUTS = [
    {"software_name": "kleborate", "dirname": "kleborate", "mask": "_kleborate", "file_ext": ".txt", "required": False},
    {"software_name": "kleborate_hamronization", "dirname": "kleborate", "mask": "_kleborate_hAMRonization", "file_ext": ".txt", "required": False},
    {"software_name": "serotypefinder_json", "dirname": "serotypefinder", "mask": "_serotypefinder", "file_ext": ".json", "required": True},
    {"software_name": "serotypefinder_meta", "dirname": "serotypefinder", "mask": "_serotypefinder_meta", "file_ext": ".json", "required": True},
    {"software_name": "shigatyper", "dirname": "shigatyper", "mask": "", "file_ext": ".tsv", "required": True},
]

# Streptococcus pyogenes / streptococcus-specific outputs.
_STREP_OUTPUTS = [
    {"software_name": "emmtyper", "dirname": "emmtyper", "mask": "_emmtyper", "file_ext": ".tsv", "required": True},
]

# post_align_qc runs for non-Streptococcus profiles only.
_POST_ALIGN_QC = [
    {"software_name": "post_align_qc", "dirname": "postalignqc", "mask": "_qc", "file_ext": ".json", "required": True},
]


def _build_outputs(*groups):
    out = []
    for group in groups:
        out.extend(group)
    return out


PROFILES = [
    {
        "profile": "staphylococcus_aureus",
        "species": "saureus",
        "outputs": _build_outputs(_COMMON_OUTPUTS, _NON_TB_OUTPUTS, _STAPH_OUTPUTS, _POST_ALIGN_QC),
    },
    {
        "profile": "escherichia_coli",
        "species": "ecoli",
        "outputs": _build_outputs(_COMMON_OUTPUTS, _NON_TB_OUTPUTS, _ECOLI_OUTPUTS, _POST_ALIGN_QC),
    },
    {
        "profile": "mycobacterium_tuberculosis",
        "species": "mtuberculosis",
        "outputs": _build_outputs(_COMMON_OUTPUTS, _TB_OUTPUTS, _POST_ALIGN_QC),
    },
    {
        "profile": "streptococcus_pyogenes",
        "species": "spyogenes",
        "outputs": _build_outputs(_COMMON_OUTPUTS, _NON_TB_OUTPUTS, _STREP_OUTPUTS),
    },
    {
        "profile": "streptococcus",
        "species": "streptococcus",
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
