# Jasentool

Multipurpose tool for jobs related to the [JASEN](https://github.com/Clinical-Genomics-Lund/JASEN) pipeline and [Bonsai](https://github.com/Clinical-Genomics-Lund/bonsai).

## Subcommands

| Subcommand | Description |
|------------|-------------|
| `find` | Query samples from MongoDB |
| `validate-pipelines` | Compare pipeline outputs against MongoDB records |
| `identify-missing` | Identify samples absent from JASEN results directory |
| `transform-file-format` | Convert cgMLST target TSV to BED format |
| `reformat-csv` | Reformat BJORN CSV/SH files for JASEN |
| `converge-catalogues` | Merge WHO, TBdb, and FoHM TB mutation catalogues |
| `post-align-qc` | Compute post-alignment QC from BAM |
| `count-reads` | Count reads in FASTQ file(s) |
| `download-ncbi` | Download genome FASTA and GFF from NCBI |
| `download-bigsdb` | Download cgMLST scheme alleles from PubMLST or BIGSdb |
| `concatenate-files` | Concatenate multiple YAML files |
| `create-yaml` | Create YAML input file for Bonsai upload |

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
:maxdepth: 1

installation
usage
```

```{toctree}
:hidden:
:caption: Reference
:maxdepth: 1

changelog
```
