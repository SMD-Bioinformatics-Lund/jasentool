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
