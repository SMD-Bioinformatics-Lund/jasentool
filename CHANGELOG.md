# Clinical-Genomics-Lund/jasentool: Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
 - Added pytests for `post-align-qc`

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

## [v0.2.0]

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
