# Jasentool

Multipurpose tool for jobs related to the [JASEN](https://github.com/Clinical-Genomics-Lund/JASEN) pipeline and [Bonsai](https://github.com/Clinical-Genomics-Lund/bonsai).

## Subcommands

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
| `concatenate-files` | Concatenate multiple YAML files |
| `count-reads` | Count reads in FASTQ file(s) |
| `create-blacklist` | Aggregate minority base frequencies across BAMs to produce a blacklist TSV |
| `create-yaml` | Create YAML input file for Bonsai upload |
| `minority-report` | Compute minority base frequency distribution from a samtools mpileup file |
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

## Quick Start

```bash
pip install jasentool
```

### Query samples from MongoDB

```bash
jasentool find \
  --query MySampleID \
  --db-name mydb \
  --db-collection samples \
  --output-file results.json
```

### Identify missing samples

```bash
jasentool identify-missing \
  --output-file missing.json \
  --db-name mydb \
  --db-collection samples \
  --analysis-dir /path/to/jasen/results
```

### Validate pipeline outputs

```bash
jasentool validate-pipelines \
  --input-dir /path/to/new/results \
  --output-dir /path/to/validation/output \
  --db-name mydb \
  --db-collection samples
```

See [Installation](installation.md) and [Usage](usage.md) for full details.

```{toctree}
:hidden:
:caption: Get started
:maxdepth: 2

installation
usage
```

```{toctree}
:hidden:
:caption: Reference
:maxdepth: 1

changelog
```
