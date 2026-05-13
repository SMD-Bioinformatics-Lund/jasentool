# Jasentool

Multipurpose tool for jobs related to the [JASEN](https://github.com/Clinical-Genomics-Lund/JASEN) pipeline and [Bonsai](https://github.com/Clinical-Genomics-Lund/bonsai).

Full documentation: [jasentool.readthedocs.io](https://jasentool.readthedocs.io).

## Installation

```
pip install jasentool
```

A conda `environment.yml` is also provided for development installs.

## Usage

```
jasentool <subcommand> [options]
```

Run `jasentool --help` to list subcommands, or `jasentool <subcommand> --help` for per-subcommand help.

### Subcommands

**Post-run analysis**

| Subcommand | Description |
|------------|-------------|
| `find` | Query samples from MongoDB |
| `identify-missing` | Identify samples absent from JASEN results directory |
| `validate-pipelines` | Compare pipeline outputs against MongoDB records |

**Pipeline processes**

| Subcommand | Description |
|------------|-------------|
| `annotate-delly` | Annotate Delly structural-variant VCFs with gene symbols and locus tags |
| `concatenate-files` | Concatenate multiple YAML files (e.g. `versions.yml`) |
| `count-reads` | Count reads in FASTQ file(s) |
| `create-blacklist` | Aggregate minority base frequencies across BAMs to produce a blacklist TSV |
| `create-yaml` | Create YAML input file for Bonsai upload |
| `minority-report` | Compute minority base frequency distribution from a `samtools mpileup` file |
| `post-align-qc` | Compute post-alignment QC from BAM |

**Site-specific hooks**

| Subcommand | Description |
|------------|-------------|
| `reformat-csv` | Reformat BJORN CSV/SH files for JASEN |

**Setup & reference data**

| Subcommand | Description |
|------------|-------------|
| `converge-catalogues` | Merge WHO, TBdb, and FoHM TB mutation catalogues |
| `download-bigsdb` | Download cgMLST scheme alleles from PubMLST or BIGSdb |
| `download-ncbi` | Download genome FASTA and GFF from NCBI |
| `transform-file-format` | Convert cgMLST target TSV to BED format |

## Quick examples

### Query samples from MongoDB

```
jasentool find \
  --query MySampleID \
  --db-name mydb \
  --db-collection samples \
  --output-file results.json
```

### Identify missing samples

```
jasentool identify-missing \
  --output-file missing.json \
  --db-name mydb \
  --db-collection samples \
  --analysis-dir /path/to/jasen/results
```

### Validate pipeline outputs

```
jasentool validate-pipelines \
  --input-dir /path/to/new/results \
  --output-dir /path/to/validation/output \
  --db-name mydb \
  --db-collection samples
```

### Compute post-alignment QC

```
jasentool post-align-qc \
  --sample-id SAMPLE_ID \
  --bam-file SAMPLE.bam \
  --output-file SAMPLE_qc.json \
  [--bed-file regions.bed] \
  [--cpus 4]
```

See the [Usage docs](https://jasentool.readthedocs.io/en/latest/usage.html) for full details.
