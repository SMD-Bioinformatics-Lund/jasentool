# Setup & reference data

Subcommands and tasks for installing and configuring JASEN.

## converge-catalogues

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

## download-bigsdb

Download cgMLST scheme alleles from PubMLST or BIGSdb Pasteur via OAuth1.

### Initial setup

Run once per site to register your API key and obtain OAuth tokens.

```bash
jasentool download-bigsdb \
  --setup \
  --site PubMLST \
  --db seqdef_db \
  --key-name mykey
```

Follow the printed URL to authorise access in your browser, then paste the verifier code when prompted. Tokens are stored in `--token-dir` (default `./.bigsdb_tokens`).

### Download scheme alleles

```bash
jasentool download-bigsdb \
  --download-scheme \
  --url https://rest.pubmlst.org/db/pubmlst_saureus_seqdef/schemes/1 \
  --site PubMLST \
  --key-name mykey \
  --output-dir /path/to/alleles
```

### Options

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

## download-ncbi

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

## transform-file-format

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

### Downloading the cgMLST targets TSV

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

## Building a Kraken2 database

### Option A: Download a pre-built database

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

### Option B: Build a custom database

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
