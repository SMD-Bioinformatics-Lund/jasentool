# Clinical-Genomics-Lund/jasentool: Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

 - `check-backup` subcommand — cross-checks Bonsai samples against the on-disk backup storage tree using each doc's `sample_id` as the filename prefix; emits per-sample summary and per-missing-file CSVs (both include `lims_id`). Filters Bonsai with `{"pipeline.analysis_profile": <PROFILE>}` and logs a warning when `species_prediction[0].scientific_name` disagrees with the profile's `species_full`. No QC filter applied (Bonsai is the curated set).
 - `jasentool/config.py` module — per-profile schedule of expected outputs as `(software_name, dirname, mask, file_ext, required)` tuples; populated from JASEN's `modules.config` for all five profiles (`staphylococcus_aureus`, `escherichia_coli`, `mycobacterium_tuberculosis`, `streptococcus_pyogenes`, `streptococcus`)
 - `jasentool/sample_utils.py` module — shared helpers extracted from `Missing` (`find_files`, `check_format`, `get_sample_name`, `parse_dir`, `filter_by_keys`) plus a new canonical `alter_sample_id(lims_id, sequencing_run)` builder
 - tqdm progress bar on `check-backup`'s per-sample scan loop, labelled with the active profile
 - Per-output stats CSV from `check-backup` (`<output>_stats.csv`) — one row per declared output with `n_missing` / `n_found` / `missing_pct`, sorted worst-first; top 10 offenders also echoed to the log
 - `-v`/`--verbose` flag on `reformat-csv` and `create-blacklist` only — the two subcommands that emit `logger.debug` records (file copies in `utils.py:129`; sample skips in `create_blacklist.py:74`)
 - `missing_software_output` column on `check-backup`'s per-sample summary CSV — semi-colon-joined list of every output identifier that was missing for that sample
 - `--check-orphans` flag on `check-backup` — emits `<stem>_orphans.csv` listing files in the backup tree under known software dirs that don't match any expected `<sample_id><mask><file_ext>`; wildcard-mask outputs are skipped with a warning

### Fixed

 - `--address`/`--uri` flag now actually overrides the MongoDB URI for `find` and `validate-pipelines`; previously it was accepted but ignored
 - Capped `pymongo<4` in `pyproject.toml` and `environment.yml` so jasentool can talk to MongoDB 3.2 (cgviz reports wire version 4; pymongo ≥ 4.9 refuses anything older than MongoDB 4.2)

### Changed

 - `Database.initialize` accepts an optional `uri` argument to override the default `mongodb://localhost:27017/`
 - `Utils.write_out_csv` and `Fix.fix_csv` now use `sample_utils.alter_sample_id` instead of duplicating the `<lims>_<seqrun>` lowercased composition
 - File matching in `check-backup` now uses `<sample_id><mask><file_ext>` with `mask` carrying the separator (e.g. `_spades`, empty for `<sample>.sig`, or `_*` for wildcard). Outputs marked `required: False` are tracked when missing but no longer flip a sample's status to FAIL.
 - Log records now go to **stdout** instead of stderr — redirect with `> log.txt` to persist (no `2>&1` needed). Group-level `--verbose` and `--log-file` flags removed; `--verbose` is per-subcommand and only attached where there are actual `logger.debug` call sites.
 - All `required: False` entries in `jasentool/config.py` are now commented out by default to keep `check-backup` runs under control on NFS-backed backup trees; uncomment the relevant lines (and consider adding a directory-listing cache for any wildcard-mask entries) before reinstating

## [1.1.0]

### Added

 - `minority-report` subcommand — computes minority base frequency distribution from a pre-computed `samtools mpileup` file (`.mpileup` or `.mpileup.gz`), with optional blacklist filtering
 - `create-blacklist` subcommand — runs mpileup and minority base distribution across a set of BAM files, then aggregates per-position frequencies to produce a minority variant blacklist TSV
 - `--plasmidfinder` flag in `create-yaml` — emits PlasmidFinder result path under the `plasmidfinder` key
 - `--plasmidfinder-genome-hits` flag in `create-yaml` — emits the path to the PlasmidFinder `Hit_in_genome_seq.fsa` under the `plasmidfinder_genome_hits` key
 - `--plasmidfinder-plasmid-seqs` flag in `create-yaml` — emits the path to the PlasmidFinder `Plasmid_seqs.fsa` under the `plasmidfinder_plasmid_seqs` key
 - `--shigatyper` flag in `create-yaml` — emits ShigaTyper result path under the `shigatyper` key (#47)
 - `--samtools-stats` and `--samtools-bedcov` flags in `create-yaml` — mutually exclusive with `--postalnqc`

### Fixed

### Changed

## [1.0.0]

### Added

 - Added `plot.py` for all plotting functions
 - Added plotting of `n_missing_loci` barplot
 - `post-align-qc` subcommand — computes post-alignment QC metrics from a BAM file
 - `count-reads` subcommand — counts reads from FASTQ file(s), outputs JSON
 - Added readthedocs
 - Added pytesting
 - Added `Dockerfile`
 - Added `download-ncbi` subcommand — downloads genome FASTA and GFF from NCBI Datasets v2 API
 - Added `download-bigsdb` subcommand — downloads cgMLST scheme alleles from PubMLST / BIGSdb Pasteur via OAuth1
 - Added `concatenate-files` subcommand — merges multiple YAML files (e.g. `versions.yml`) into one output YAML
 - Added `create-yaml` subcommand — creates a YAML input file for Bonsai upload from sample metadata and analysis result paths
 - Added GA workflows for publishing to dockerhub and pypi
 - Added pytest for `download-ncbi` subcommand
 - Added conda `environment.yml` for installation
 - Added `annotate-delly` subcommand — annotates Delly structural-variant VCFs with gene symbols and locus tags from a tabix-indexed BED file
 - Added pytests for `post-align-qc` and `count-reads` subcommands using simulated S. aureus fixture data
 - Added S. aureus simulated FASTQ and BAM fixtures (`saureus_sim_R1.fastq.gz`, `saureus_sim_R2.fastq.gz`, `saureus_test_1.bam`) for testing

### Fixed

 - Fixed cronjob bugs
 - Fixed cronjob missing execution
 - Fixed parsing of jasen `.json` files

### Changed

 - Changed cronjob to use environmental variables
 - Changed default `--remote_hostname`
 - `missing` → `identify-missing`
 - `convert` → `transform-file-format`
 - `fix` → `reformat-csv`
 - `converge` → `converge-catalogues`
 - All subcommand argument names changed from underscore style (`--db_name`) to hyphen style (`--db-name`)
 - Removed `insert` subcommand
 - Change sambamba for pysam
 - Removed picard hs metrics and `--reference` arg
 - `download_ncbi.py` → `ncbi.py` (class `DownloadNcbi` → `NCBI`), `download_bigsdb.py` → `bigsdb.py` (class `DownloadBigsdb` → `BIGSdb`) — renamed to match module naming convention
 - Removed `download-krakendb` subcommand; Kraken2 DB building is now documented as a Singularity workflow in `docs/usage.md`
 - `Utils.download_and_save_file` upgraded with exponential-backoff retry logic (`max_retries` parameter); `Utils.unzip` now returns bool and handles corrupt archives
 - `count-reads`: now reads in binary chunks and counts newlines instead of iterating line-by-line in text mode to reduce overhead
 - `annotate-delly`: VCF and TabixFile handles now explicitly closed; writer wrapped in try/finally; tabix index existence validated before opening BED file

## [0.2.0]

### Added

 - Added tb validation notebook
 - Added output csv for failed validation samples
 - Added differential matrix for validation
 - Added saureus validation notebook
 - Added `--generate_matrix` argument to cli
 - Added `alter_sample_id` filter
 - Added summed differential matrix
 - Added mean coverage plot
 - Added jitter to mean coverage boxplot

### Fixed

 - Fixed `pyproject.toml` setuptools bug
 - Fixed cgmlst comparison and plots
 - Fixed `fix` subarg
 - Fixed TN/TP/FN/FP plots

### Changed

 - Changed id format for fix and missing
 - Changed matrix to boxplot, jitter, and annotate

## [0.1.0] - 2024-05-22

### Added

 - `find` — query samples from MongoDB
 - `insert` — insert JSON results into MongoDB
 - `validate` — compare pipeline outputs against MongoDB records
 - `missing` — identify samples absent from JASEN results directory
 - `convert` — convert cgMLST target TSV to BED format
 - `fix` — reformat BJORN CSV/SH files for JASEN
 - `converge` — merge WHO, TBdb, and FoHM TB mutation catalogues
 - `qc` — compute post-alignment QC from BAM
 - Pylint GitHub Actions workflow
 - `pyproject.toml` replacing `setup.py`
 - `sequencing_run` and `clarity_sample_id` fields in outputs
