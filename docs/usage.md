# Usage

## Overview

```
jasentool <subcommand> [options]
```

Run `jasentool --help` to list subcommands, or `jasentool <subcommand> --help` for per-subcommand help.

---

## find

Query samples from a MongoDB collection.

```
jasentool find --query <QUERY> [--query ...] --db_name <DB> --db_collection <COLLECTION>
               (--output_file <FILE> | --output_dir <DIR>)
               [--address <URI>] [--prefix <PREFIX>] [--combined_output]
```

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `-q`/`--query` | Yes | — | One or more sample queries |
| `--db_name` | Yes | — | MongoDB database name |
| `--db_collection` | Yes | — | MongoDB collection name |
| `--output_file`/`--output_dir` | Yes (one) | — | Output file or directory |
| `--address`/`--uri` | No | `mongodb://localhost:27017/` | MongoDB host address |
| `--prefix` | No | `jasentool_results_` | Prefix for output files |
| `--combined_output` | No | False | Combine all outputs into one file |

**Example**

```bash
jasentool find \
  --query MySample \
  --db_name mydb \
  --db_collection samples \
  --output_file results.json
```

---

## insert

Insert JSON sample results into a MongoDB collection.

```
jasentool insert (--input_file <FILE> [...]| --input_dir <DIR>)
                 --db_name <DB> --db_collection <COLLECTION>
                 [--address <URI>] [--combined_output]
```

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `-i`/`--input_file` | Yes (or `--input_dir`) | — | Path(s) to JSON file(s) |
| `--input_dir` | Yes (or `--input_file`) | — | Directory containing sample files |
| `--db_name` | Yes | — | MongoDB database name |
| `--db_collection` | Yes | — | MongoDB collection name |
| `--address`/`--uri` | No | `mongodb://localhost:27017/` | MongoDB host address |
| `--combined_output` | No | False | Combine all outputs into one file |

**Example**

```bash
jasentool insert \
  --input_file sample.json \
  --db_name mydb \
  --db_collection samples
```

---

## validate

Compare new pipeline outputs against existing MongoDB records.

```
jasentool validate (--input_file <FILE> [...] | --input_dir <DIR>)
                   (--output_file <FILE> | --output_dir <DIR>)
                   --db_name <DB> --db_collection <COLLECTION>
                   [--address <URI>] [--prefix <PREFIX>]
                   [--combined_output] [--generate_matrix]
```

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `-i`/`--input_file` | Yes (or `--input_dir`) | — | Input filepath(s) |
| `--input_dir` | Yes (or `--input_file`) | — | Directory containing sample files |
| `--output_file`/`--output_dir` | Yes (one) | — | Output file or directory |
| `--db_name` | Yes | — | MongoDB database name |
| `--db_collection` | Yes | — | MongoDB collection name |
| `--address`/`--uri` | No | `mongodb://localhost:27017/` | MongoDB host address |
| `--prefix` | No | `jasentool_results_` | Prefix for output files |
| `--combined_output` | No | False | Combine all outputs into one file |
| `--generate_matrix` | No | False | Generate cgMLST matrix |

**Example**

```bash
jasentool validate \
  --input_dir /new/results \
  --output_dir /validation/output \
  --db_name mydb \
  --db_collection samples \
  --generate_matrix
```

---

## missing

Identify samples absent from the JASEN results directory.

```
jasentool missing --output_file <FILE> --db_name <DB> --db_collection <COLLECTION>
                  [--analysis_dir <DIR>] [--restore_dir <DIR>] [--restore_file <FILE>]
                  [--missing_log <FILE>] [--assay <ASSAY>] [--platform <PLATFORM>]
                  [--sample_sheet] [--alter_sample_id]
```

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `-o`/`--output_file` | Yes | — | Output file path |
| `--db_name` | Yes | — | MongoDB database name |
| `--db_collection` | Yes | — | MongoDB collection name |
| `--analysis_dir` | No | — | Analysis results directory containing JASEN results |
| `--restore_dir` | No | `/fs2/seqdata/restored` | Directory for restored spring files |
| `--restore_file` | No | — | Output bash shell script (.sh) |
| `--missing_log` | No | `missing_samples.log` | File to log missing samples |
| `--assay` | No | `jasen-saureus-dev` | JASEN assay name |
| `--platform` | No | `illumina` | Sequencing platform |
| `--sample_sheet` | No | False | Use sample sheet input |
| `--alter_sample_id` | No | False | Alter sample ID to LIMS ID + sequencing run |

**Example**

```bash
jasentool missing \
  --output_file missing.json \
  --db_name mydb \
  --db_collection samples \
  --analysis_dir /fs1/results/jasen
```

---

## convert

Convert a cgMLST target TSV file to BED format (or another output format).

```
jasentool convert --input_file <FILE> [...] --output_file <FILE>
                  [--out_format <FORMAT>] [--accession <ACCESSION>]
```

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `-i`/`--input_file` | Yes | — | Path to targets TSV file |
| `-o`/`--output_file` | Yes | — | Output file path |
| `-f`/`--out_format` | No | `bed` | Output format |
| `-a`/`--accession` | No | — | Accession number |

**Example**

```bash
jasentool convert \
  --input_file targets.tsv \
  --output_file targets.bed
```

---

## fix

Reformat a BJORN microbiology CSV (and optionally SH) file for JASEN.

```
jasentool fix --csv_file <FILE> --output_file <FILE>
              [--sh_file <FILE>] [--remote_dir <DIR>] [--remote_hostname <HOST>]
              [--remote] [--auto_start] [--alter_sample_id]
```

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `--csv_file` | Yes | — | Path to BJORN CSV file |
| `-o`/`--output_file` | Yes | — | Path to fixed output CSV file |
| `--sh_file` | No | None | Path to BJORN SH file |
| `--remote_dir` | No | `/fs1/bjorn/jasen` | Remote directory for spring files |
| `--remote_hostname` | No | `rs-fe1.lunarc.lu.se` | Remote hostname |
| `--remote` | No | False | Enable remote copy |
| `--auto_start` | No | False | Automatically start after fix |
| `--alter_sample_id` | No | False | Alter sample ID to LIMS ID + sequencing run |

**Example**

```bash
jasentool fix \
  --csv_file bjorn.csv \
  --output_file fixed.csv \
  --sh_file bjorn.sh \
  --remote
```

---

## converge

Merge WHO, TBdb, and FoHM TB mutation catalogues into a unified TBProfiler database.

```
jasentool converge [--output_dir <DIR>] [--save_dbs]
```

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `--output_dir` | No | — | Directory to write output files |
| `--save_dbs` | No | False | Save all intermediary databases |

**Example**

```bash
jasentool converge --output_dir /path/to/output --save_dbs
```

---

## qc

Compute post-alignment QC metrics from a BAM file.

```
jasentool qc --sample_id <ID> --bam_file <FILE> --reference <FILE> --output_file <FILE>
             [--bed_file <FILE>] [--baits_file <FILE>] [--cpus <N>]
```

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `--sample_id` | Yes | — | Sample ID |
| `--bam_file` | Yes | — | Input BAM file |
| `--reference` | Yes | — | Reference FASTA file |
| `-o`/`--output_file` | Yes | — | Path to QC JSON output file |
| `--bed_file` | No | — | Input BED file |
| `--baits_file` | No | None | Input baits file |
| `--cpus` | No | `2` | Number of CPUs |

**Example**

```bash
jasentool qc \
  --sample_id SAMPLE001 \
  --bam_file aligned.bam \
  --reference reference.fasta \
  --output_file qc.json \
  --bed_file targets.bed \
  --cpus 4
```

---

## Upcoming subcommands (unreleased)

The following subcommands are planned for the next release and will use hyphen-style argument names.

### post-align-qc

Compute post-alignment QC metrics from a BAM file (replacement for `qc` with updated interface).

```
jasentool post-align-qc --sample-id <ID> --bam-file <FILE> --reference <FILE>
                         --output-file <FILE> [--bed-file <FILE>]
                         [--baits-file <FILE>] [--cpus <N>]
```

### count-reads

Count reads from one or more FASTQ files and output a JSON summary.

```
jasentool count-reads --input-file <FILE> [...] --output-file <FILE>
```
