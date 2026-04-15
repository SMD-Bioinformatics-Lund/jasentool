# Pipeline processes

Subcommands invoked as individual processes during JASEN pipeline execution.

## concatenate-files

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

## count-reads

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

## create-yaml

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
| `--quast` | QUAST output |
| `--ref-genome-annotation` | Reference genome annotation |
| `--ref-genome-sequence` | Reference genome FASTA |
| `--resfinder` | ResFinder output |
| `--samtools` | Samtools stats output |
| `--samtools-bedcov` | Samtools bedcov output |
| `--samtools-stats` | Samtools stats (detailed) output |
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

## annotate-delly

Annotate a Delly structural-variant VCF/BCF with `gene` and `locus_tag` INFO fields derived
from a tabix-indexed BED file. Handles chromosome name mismatches between the VCF and BED
(single-contig BED files are remapped automatically).

```
jasentool annotate-delly -v <VCF> -b <BED> -o <OUTPUT>
```

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `-v`/`--vcf` | Yes | — | Delly VCF/BCF to annotate |
| `-b`/`--bed` | Yes | — | Tabix-indexed BED file with gene annotations |
| `-o`/`--output` | Yes | — | Output annotated VCF path |

**Example**

```bash
jasentool annotate-delly \
  -v delly.bcf \
  -b converged_who_fohm_tbdb.bed.gz \
  -o delly_annotated.vcf
```

## create-blacklist

Build a minority variant blacklist by running `samtools mpileup` and minority base distribution
analysis across a set of BAM files, then aggregating positions that exceed a frequency threshold
in enough samples. The resulting TSV can be passed to `minority-report` via `--blacklist` to
exclude known high-noise positions.

Intermediate per-sample mpileup and distribution files are written to `--output-dir`. Only
samples whose stem matches `--sample-pattern` contribute to the final blacklist.

```
jasentool create-blacklist (--input-file <FILE> | --input-dir <DIR>)
                            --output-dir <DIR> -o <FILE>
                            [--bed-file <FILE>] [--samtools <PATH>]
                            [--sample-pattern <REGEX>]
                            [--min-freq <FLOAT>] [--min-count <INT>]
```

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `-i`/`--input-file` | Yes (or `--input-dir`) | — | Text file of BAM paths, one per line |
| `--input-dir` | Yes (or `--input-file`) | — | Directory containing `*.bam` files |
| `--output-dir` | Yes | — | Directory for intermediate files |
| `-o`/`--output-file` | Yes | — | Output blacklist TSV path |
| `--bed-file` | No | — | BED file passed to `samtools mpileup -l` |
| `--samtools` | No | `samtools` | Path or name of the samtools executable |
| `--sample-pattern` | No | `.*` | Regex to filter which sample names contribute to the blacklist |
| `--min-freq` | No | `0.05` | Minimum minority frequency to count a position |
| `--min-count` | No | `5` | Minimum number of samples a position must appear in |

**Example**

```bash
# From a directory of BAM files, only including samples matching ^[0-9]{2}MT
jasentool create-blacklist \
  --input-dir /data/bams \
  --output-dir /data/blacklist_work \
  -o blacklist.tsv \
  --bed-file targets.bed \
  --sample-pattern '^[0-9]{2}MT'
```

## minority-report

Compute minority base frequency distribution from a pre-computed `samtools mpileup` file. For each
position with coverage between 30 and 100, the second-highest base count divided by coverage is
recorded as the minority frequency. Outputs two files:

- `<output>` — one minority frequency per line (no position)
- `<output>.withpos` — tab-separated `position\tminority_freq`

```
jasentool minority-report --mpileup <FILE> -o <OUTPUT_STEM> [--blacklist <FILE>]
```

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `--mpileup` | Yes | — | Input mpileup file (`.mpileup` or `.mpileup.gz`) |
| `-o`/`--output` | Yes | — | Output path stem (no extension) |
| `--blacklist` | No | — | Blacklist TSV of positions to exclude (see `create-blacklist`) |

**Example**

```bash
jasentool minority-report \
  --mpileup sample.mpileup.gz \
  --blacklist blacklist.tsv \
  -o sample_minority_dist
```

## post-align-qc

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
