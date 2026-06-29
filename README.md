# Jasentool

Multipurpose tool for jobs related to the [JASEN](https://github.com/Clinical-Genomics-Lund/JASEN) pipeline and [Bonsai](https://github.com/Clinical-Genomics-Lund/bonsai).

Full documentation: [jasentool.readthedocs.io](https://jasentool.readthedocs.io).

## Installation

```
pip install jasentool
```

### Older Linux distributions (recommended: conda)

On hosts with **glibc < 2.28** (Ubuntu < 18.04, RHEL/CentOS < 8, Debian < 10) pip will not find binary wheels for current pandas / numpy on Python 3.12 and will fall back to source builds that require GCC ≥ 9.3. Use conda instead — conda-forge ships its own compatible binaries:

```
git clone https://github.com/SMD-Bioinformatics-Lund/jasentool.git
cd jasentool
conda env create -f environment.yml
conda activate jasentool
```

`environment.yml` installs every binary-heavy dependency (pandas, numpy, matplotlib, biopython, pysam, cyvcf2, openpyxl) from conda-forge and then performs an editable pip install of jasentool itself.

## Usage

```
jasentool <subcommand> [options]
```

Run `jasentool --help` to list subcommands, or `jasentool <subcommand> --help` for per-subcommand help.

### Subcommands

**Post-run analysis**

| Subcommand | Description |
|------------|-------------|
| `check-backup` | Cross-check Bonsai samples against the backup storage tree |
| `rerun-chewbbaca` | Re-run chewBBACA AlleleCall on a check-backup masked-assemblies CSV |
| `compare-distances` | Build cgMLST distance matrices for two chewBBACA tables and their difference |
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

### Cross-check backup storage

```
jasentool check-backup \
  --profile staphylococcus_aureus \
  --backup-dir /backup/jasen \
  --db-name bonsai \
  --db-collection samples \
  --address mongodb://bonsai.host:27017/ \
  -o backup_status.csv
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
