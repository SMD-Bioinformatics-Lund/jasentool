# Usage

## Overview

```
jasentool <subcommand> [options]
```

Run `jasentool --help` to list subcommands, or `jasentool <subcommand> --help` for per-subcommand help.

---

## Post-run analysis

Subcommands for querying and analysing results after JASEN runs.

### find

Query samples from a MongoDB collection.

```
jasentool find --query <QUERY> [--query ...] --db-name <DB> --db-collection <COLLECTION>
               (--output-file <FILE> | --output-dir <DIR>)
               [--address <URI>] [--prefix <PREFIX>] [--combined-output]
```

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `-q`/`--query` | Yes | — | One or more sample queries |
| `--db-name` | Yes | — | MongoDB database name |
| `--db-collection` | Yes | — | MongoDB collection name |
| `--output-file`/`--output-dir` | Yes (one) | — | Output file or directory |
| `--address`/`--uri` | No | `mongodb://localhost:27017/` | MongoDB host address |
| `--prefix` | No | `jasentool_results_` | Prefix for output files |
| `--combined-output` | No | False | Combine all outputs into one file |

**Example**

```bash
jasentool find \
  --query MySample \
  --db-name mydb \
  --db-collection samples \
  --output-file results.json
```

---

### identify-missing

Identify samples absent from the JASEN results directory.

```
jasentool identify-missing --output-file <FILE> --db-name <DB> --db-collection <COLLECTION>
                            [-i <FILE> [...]]
                            [--analysis-dir <DIR>] [--restore-dir <DIR>] [--restore-file <FILE>]
                            [--missing-log <FILE>] [--assay <ASSAY>] [--platform <PLATFORM>]
                            [--sample-sheet] [--alter-sample-id]
```

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `-o`/`--output-file` | Yes | — | Output file path |
| `--db-name` | Yes | — | MongoDB database name |
| `--db-collection` | Yes | — | MongoDB collection name |
| `-i`/`--input-file` | No | — | Input filepath(s) |
| `--analysis-dir` | No | — | Analysis results directory containing JASEN results |
| `--restore-dir` | No | `/fs2/seqdata/restored` | Directory for restored spring files |
| `--restore-file` | No | — | Output bash shell script (.sh) |
| `--missing-log` | No | `missing_samples.log` | File to log missing samples |
| `--assay` | No | `jasen-saureus-dev` | JASEN assay name |
| `--platform` | No | `illumina` | Sequencing platform |
| `--sample-sheet` | No | False | Use sample sheet input |
| `--alter-sample-id` | No | False | Alter sample ID to LIMS ID + sequencing run |

**Example**

```bash
jasentool identify-missing \
  --output-file missing.json \
  --db-name mydb \
  --db-collection samples \
  --analysis-dir /fs1/results/jasen
```

---

### validate-pipelines

Compare new pipeline outputs against existing MongoDB records.

```
jasentool validate-pipelines (--input-file <FILE> [...] | --input-dir <DIR>)
                              (--output-file <FILE> | --output-dir <DIR>)
                              --db-name <DB> --db-collection <COLLECTION>
                              [--address <URI>] [--prefix <PREFIX>]
                              [--combined-output] [--generate-matrix]
```

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `-i`/`--input-file` | Yes (or `--input-dir`) | — | Input filepath(s) |
| `--input-dir` | Yes (or `--input-file`) | — | Directory containing sample files |
| `--output-file`/`--output-dir` | Yes (one) | — | Output file or directory |
| `--db-name` | Yes | — | MongoDB database name |
| `--db-collection` | Yes | — | MongoDB collection name |
| `--address`/`--uri` | No | `mongodb://localhost:27017/` | MongoDB host address |
| `--prefix` | No | `jasentool_results_` | Prefix for output files |
| `--combined-output` | No | False | Combine all outputs into one file |
| `--generate-matrix` | No | False | Generate cgMLST matrix |

**Example**

```bash
jasentool validate-pipelines \
  --input-dir /new/results \
  --output-dir /validation/output \
  --db-name mydb \
  --db-collection samples \
  --generate-matrix
```

---

## Pipeline processes

Subcommands invoked as individual processes during JASEN pipeline execution.

### concatenate-files

Merge multiple YAML files (e.g. `versions.yml` outputs from pipeline runs) into a single YAML file. Later files override keys from earlier files.

```
jasentool concatenate-files -i <FILE> [-i <FILE> ...] -o <FILE>
```

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `-i`/`--input` | Yes (multiple) | — | Input YAML file(s) to concatenate |
| `-o`/`--output-file` | Yes | — | Path to output YAML file |

**Example**

```bash
jasentool concatenate-files \
  -i run1/versions.yml \
  -i run2/versions.yml \
  -o merged_versions.yml
```

---

### count-reads

Count reads from one or more FASTQ files and output a JSON summary.

```
jasentool count-reads --fastq1 <FILE> [--fastq2 <FILE>] --output-file <FILE>
                      [--sample-id <ID>]
```

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `--fastq1` | Yes | — | Path to R1 FASTQ file |
| `--fastq2` | No | — | Path to R2 FASTQ file (paired-end) |
| `-o`/`--output-file` | Yes | — | Path to JSON output file |
| `--sample-id` | No | — | Sample ID |

**Example**

```bash
jasentool count-reads \
  --fastq1 sample_R1.fastq.gz \
  --fastq2 sample_R2.fastq.gz \
  --output-file read_counts.json \
  --sample-id SAMPLE001
```

---

### create-yaml

Create a YAML input file for Bonsai upload from sample metadata and analysis result file paths. Builds IGV annotation entries automatically from BAM/BAI, VCF, and BED inputs.

```
jasentool create-yaml --sample-id <ID> --sample-name <NAME> --groups <GROUP> [--groups ...] -o <FILE>
                      [analysis result options ...]
```

**Required options**

| Argument | Description |
|----------|-------------|
| `--sample-id` | Sample ID |
| `--sample-name` | Sample name |
| `--groups` | Sample group(s); repeat for multiple |
| `-o`/`--output` | Output YAML file path |

**Analysis result options (all optional, all accept a file path)**

| Argument | Description |
|----------|-------------|
| `--amrfinder` | AMRFinder output |
| `--chewbbaca` | chewBBACA cgMLST output |
| `--emmtyper` | Emmtyper output |
| `--gambitcore` | GAMBIT core output |
| `--kleborate` | Kleborate output |
| `--kleborate-hamronization` | Kleborate hAMRonization output |
| `--kraken` | Kraken2 output |
| `--mlst` | MLST output |
| `--mykrobe` | Mykrobe output |
| `--nanoplot` | NanoPlot output |
| `--nextflow-run-info` | Nextflow run info JSON |
| `--postalnqc` | Post-alignment QC output |
| `--quast` | QUAST output |
| `--ref-genome-annotation` | Reference genome annotation |
| `--ref-genome-sequence` | Reference genome FASTA |
| `--resfinder` | ResFinder output |
| `--samtools` | Samtools stats output |
| `--sccmec` | SCCmec output |
| `--serotypefinder` | SerotypeFinder output |
| `--shigapass` | ShigaPass output |
| `--ska-index` | SKA index file |
| `--sourmash-signature` | Sourmash signature file |
| `--spatyper` | spaTyper output |
| `--tbprofiler` | TBProfiler output |
| `--virulencefinder` | VirulenceFinder output |

**IGV annotation options (all optional)**

| Argument | Description |
|----------|-------------|
| `--bam` | BAM alignment file (creates IGV alignment track) |
| `--bai` | BAM index file |
| `--vcf` | VCF variant file (creates IGV variant track) |
| `--tb-grading-rules-bed` | TB grading rules BED file (creates IGV BED track) |
| `--tbdb-bed` | TB database BED file (creates IGV BED track) |

**Other options**

| Argument | Description |
|----------|-------------|
| `--lims-id` | LIMS ID |
| `--software-info` | Software info file(s); repeat for multiple |

**Example**

```bash
jasentool create-yaml \
  --sample-id SAMP001 \
  --sample-name "Sample 001" \
  --groups wgs \
  --bam aligned.bam \
  --bai aligned.bam.bai \
  --mlst mlst.json \
  --kraken kraken_report.txt \
  -o input.yml
```

---

### post-align-qc

Compute post-alignment QC metrics from a BAM file.

```
jasentool post-align-qc --sample-id <ID> --bam-file <FILE> --output-file <FILE>
                         [--bed-file <FILE>] [--cpus <N>]
```

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `--sample-id` | Yes | — | Sample ID |
| `--bam-file` | Yes | — | Input BAM file |
| `-o`/`--output-file` | Yes | — | Path to QC JSON output file |
| `--bed-file` | No | — | Input BED file |
| `--cpus` | No | `2` | Number of CPUs |

**Example**

```bash
jasentool post-align-qc \
  --sample-id SAMPLE001 \
  --bam-file aligned.bam \
  --output-file qc.json \
  --bed-file targets.bed \
  --cpus 4
```

---

## Site-specific hooks

`reformat-csv` was built specifically for Clinical Genomics Lund's BJORN system.

### reformat-csv

Reformat a BJORN microbiology CSV (and optionally SH) file for JASEN.

```
jasentool reformat-csv --csv-file <FILE> --output-file <FILE>
                        [--sh-file <FILE>] [--remote-dir <DIR>] [--remote-hostname <HOST>]
                        [--remote] [--auto-start] [--alter-sample-id]
```

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `--csv-file` | Yes | — | Path to BJORN CSV file |
| `-o`/`--output-file` | Yes | — | Path to fixed output CSV file |
| `--sh-file` | No | None | Path to BJORN SH file |
| `--remote-dir` | No | `/fs1/bjorn/jasen` | Remote directory for spring files |
| `--remote-hostname` | No | `rs-fe1.lunarc.lu.se` | Remote hostname |
| `--remote` | No | False | Enable remote copy |
| `--auto-start` | No | False | Automatically start after fix |
| `--alter-sample-id` | No | False | Alter sample ID to LIMS ID + sequencing run |

**Example**

```bash
jasentool reformat-csv \
  --csv-file bjorn.csv \
  --output-file fixed.csv \
  --sh-file bjorn.sh \
  --remote
```

---

## Setup & reference data

Subcommands and tasks used when installing and configuring JASEN.

### converge-catalogues

Merge WHO, TBdb, and FoHM TB mutation catalogues into a unified TBProfiler database.

```
jasentool converge-catalogues [--output-dir <DIR>] [--save-dbs]
```

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `--output-dir` | No | — | Directory to write output files |
| `--save-dbs` | No | False | Save all intermediary databases |

**Example**

```bash
jasentool converge-catalogues --output-dir /path/to/output --save-dbs
```

---

### download-bigsdb

Download cgMLST scheme alleles from PubMLST or BIGSdb Pasteur via OAuth1.

#### Initial setup

Run once per site to register your API key and obtain OAuth tokens.

```bash
jasentool download-bigsdb \
  --setup \
  --site PubMLST \
  --db seqdef_db \
  --key-name mykey
```

Follow the printed URL to authorise access in your browser, then paste the verifier code when prompted. Tokens are stored in `--token-dir` (default `./.bigsdb_tokens`).

#### Download scheme alleles

```bash
jasentool download-bigsdb \
  --download-scheme \
  --url https://rest.pubmlst.org/db/pubmlst_saureus_seqdef/schemes/1 \
  --site PubMLST \
  --key-name mykey \
  --output-dir /path/to/alleles
```

#### Options

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `--url` | Conditional | — | API endpoint URL (required for `--download-scheme`) |
| `--site` | No | — | BIGSdb site: `PubMLST` or `Pasteur` |
| `--key-name` | Yes | — | API key name (unique per site) |
| `--output-dir` | No | — | Directory for per-locus FASTA files (`--download-scheme`) |
| `--token-dir` | No | `./.bigsdb_tokens` | Token storage directory |
| `--db` | No | — | Database config name (setup only) |
| `--setup` | No | False | Run initial OAuth1 setup |
| `--download-scheme` | No | False | Download all scheme loci |
| `--force` | No | False | Re-download existing files (`--download-scheme`) |
| `--cron` | No | False | Non-interactive / cron mode |
| `--method` | No | `GET` | HTTP method: `GET` or `POST` |
| `--output-file` | No | — | Save single API response to this file |

---

### download-ncbi

Download genome FASTA and GFF from the NCBI Datasets v2 API.

```
jasentool download-ncbi --accession <ACC> [--accession ...] --output-dir <DIR>
                        [--bwa-index] [--fai-index] [--clean]
```

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `-i`/`--accession` | Yes | — | NCBI accession number(s); repeat for multiple |
| `-o`/`--output-dir` | Yes | — | Output directory |
| `--bwa-index` | No | False | Run `bwa index` on the downloaded FASTA |
| `--fai-index` | No | False | Run `samtools faidx` on the downloaded FASTA |
| `--clean` | No | False | Clear output directory before downloading |

**Example**

```bash
jasentool download-ncbi \
  --accession GCF_000013425.1 \
  --output-dir /path/to/references \
  --fai-index
```

---

### transform-file-format

Convert a cgMLST target TSV file to BED format (or another output format).

```
jasentool transform-file-format -i <FILE> [...] -o <FILE>
                                 [-f <FORMAT>] [-a <ACCESSION>]
```

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `-i`/`--input-file` | Yes | — | Path to targets TSV file |
| `-o`/`--output-file` | Yes | — | Output file path |
| `-f`/`--out-format` | No | `bed` | Output format |
| `-a`/`--accession` | No | — | Chromosome/contig accession for the BED `chrom` column |

#### Downloading the cgMLST targets TSV

The input TSV is the locus table for your organism's cgMLST scheme on [cgMLST.org](https://www.cgmlst.org). To download it:

1. Navigate to your organism's schema page, e.g. `https://www.cgmlst.org/ncs/schema/<SCHEMA_NAME>/locus/` (the schema name differs per organism — for *S. aureus* it is `Saureus4059`).
2. Click the **Download table as CSV** button.

The downloaded file has a `.csv` extension but is tab-separated. Pass it directly to `--input-file`.

**Example**

```bash
jasentool transform-file-format \
  --input-file Staphylococcus_aureus_cgMLST.csv \
  --output-file targets.bed \
  --accession NC_002951.2
```

---

### Building a Kraken2 database (via Singularity)

#### Option A: Download a pre-built database (recommended)

Pre-built databases are ready to use with no build step — just download and extract.

Full index listing: `https://benlangmead.github.io/aws-indexes/k2`

| Database | Index size | RAM needed | Contents |
|----------|------------|------------|---------|
| `Standard` | 96.8 GB | ~96 GB | Archaea, bacteria, viral, plasmid, human, UniVec_Core |
| `Standard-16` | 14.9 GB | ~16 GB | Same libraries, k-mer-filtered to fit 16 GB |
| `Standard-8` | 7.5 GB | ~8 GB | Same libraries, k-mer-filtered to fit 8 GB |
| `PlusPF` | 103.4 GB | ~103 GB | Standard + protozoa & fungi |
| `Viral` | 0.6 GB | ~1 GB | RefSeq viral only |

**Example (Standard-8):**

```bash
# Download (check https://benlangmead.github.io/aws-indexes/k2 for the latest URL)
wget https://genome-idx.s3.amazonaws.com/kraken/k2_standard_08gb_<DATE>.tar.gz
mkdir -p /path/to/krakendb
tar -xzf k2_standard_08gb_<DATE>.tar.gz -C /path/to/krakendb

# Run classification
singularity exec kraken2.sif kraken2 \
  --db /path/to/krakendb \
  --paired --gzip-compressed \
  sample_R1.fastq.gz sample_R2.fastq.gz \
  --output kraken_output.txt \
  --report kraken_report.txt
```

#### Option B: Build a custom database from scratch

jasentool does not wrap `kraken2-build`. Use the official Kraken2 Singularity image directly:

```bash
# Pull the image (once)
singularity pull kraken2.sif docker://staphb/kraken2:latest

# Download NCBI taxonomy
singularity exec kraken2.sif kraken2-build \
  --download-taxonomy --db /path/to/krakendb

# Download one or more libraries (repeat per library)
singularity exec kraken2.sif kraken2-build \
  --download-library bacteria --db /path/to/krakendb

singularity exec kraken2.sif kraken2-build \
  --download-library viral --db /path/to/krakendb

singularity exec kraken2.sif kraken2-build \
  --download-library human --db /path/to/krakendb

# Build the database
singularity exec kraken2.sif kraken2-build \
  --build --db /path/to/krakendb --threads 8
```

Available library names: `archaea`, `bacteria`, `plasmid`, `viral`, `human`, `fungi`, `plant`, `protozoa`, `nr`, `nt`, `UniVec`, `UniVec_Core`.
