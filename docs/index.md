# Jasentool

Multipurpose tool for jobs related to the [JASEN](https://github.com/Clinical-Genomics-Lund/JASEN) pipeline and [Bonsai](https://github.com/Clinical-Genomics-Lund/bonsai).

## Subcommands

| Subcommand | Description |
|------------|-------------|
| `find` | Query samples from MongoDB |
| `insert` | Insert JSON results into MongoDB |
| `validate` | Compare pipeline outputs against MongoDB records |
| `missing` | Identify samples absent from JASEN results directory |
| `convert` | Convert cgMLST target TSV to BED format |
| `fix` | Reformat BJORN CSV/SH files for JASEN |
| `converge` | Merge WHO, TBdb, and FoHM TB mutation catalogues |
| `qc` | Compute post-alignment QC from BAM |

## Quick Start

```bash
pip install jasentool
```

### Query samples from MongoDB

```bash
jasentool find \
  --query MySampleID \
  --db_name mydb \
  --db_collection samples \
  --output_file results.json
```

### Identify missing samples

```bash
jasentool missing \
  --output_file missing.json \
  --db_name mydb \
  --db_collection samples \
  --analysis_dir /path/to/jasen/results
```

### Validate pipeline outputs

```bash
jasentool validate \
  --input_dir /path/to/new/results \
  --output_dir /path/to/validation/output \
  --db_name mydb \
  --db_collection samples
```

See [Installation](installation.md) and [Usage](usage.md) for full details.
