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
    _out("gambitcore", "gambitcore", "_gambitcore", ".tsv"),
    _out("ska", "ska", "_ska_index", ".skf"),
    _out("create_yaml", "analysis_yaml", "_bonsai", ".yaml"),
    _out("format_jasen", "analysis_result", "_result", ".json"),
    _out("format_cdm", "cdm_input", "_qc_result", ".json"),
    _out("export_to_cdm", "qc", "", ".cdmpy"),
    _out("save_analysis_metadata", "analysis_metadata", "_analysis_meta", ".json"),
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
    # _out("resfinder_point_table", "resfinder", "_point_table", ".txt", required=False),
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
    _out("freebayes", "vcf", "_freebayes", ".vcf"),
    # Optional / feature- and platform-gated entries — uncomment if/when needed.
    # Non-TB assembly variants (one will run depending on platform / feature flags)
    # _out("spades", "fasta", "_spades", ".fasta", required=False),
    # _out("skesa", "fasta", "_skesa", ".fasta", required=False),
    # _out("flye", "fasta", "_flye", ".fasta", required=False),
    # _out("medaka", "fasta", "_medaka", ".fasta", required=False),
    # Non-TB alignment / variant ancillaries (gated by platform / use_masking)
    # _out("bwa_mem_ref", "bam", "_bwa", ".bam", required=False),
    # _out("clair3_ref", "vcf", "_clair3", ".vcf.gz", required=False),
    # _out("mask_polymorph", "mask", "_mask", ".fasta", required=False),
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
    _out("sccmec", "sccmec", "_sccmec", ".tsv"),
    _out("spatyper", "spatyper", "_spatyper", ".tsv"),
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

# post_align_qc runs for non-Streptococcus profiles only.
_POST_ALIGN_QC = [
    _out("post_align_qc", "postalignqc", "_qc", ".json"),
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
