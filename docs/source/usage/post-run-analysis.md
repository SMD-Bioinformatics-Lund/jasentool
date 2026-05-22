# Post-run analysis

Subcommands for querying and analysing results after JASEN runs.

## find

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

## identify-missing

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

## check-backup

Cross-checks samples in the **Bonsai** MongoDB against the on-disk backup storage tree to find samples whose expected JASEN outputs are not yet backed up. Bonsai is the authoritative list of curated samples; each doc's `sample_id` is the filename prefix used in the backup tree.

Backup tree layout: `<backup-dir>/<species_shortname>/<software_dirname>/<file>`. Species shortnames (e.g. `saureus`, `ecoli`) come from `jasentool/config.py` — that module holds the per-profile schedule of expected outputs as `(software_name, dirname, mask, file_ext, required)` tuples. Edit it and reinstall the package to change which outputs are checked.

Files are matched per sample as `<sample_id><mask><file_ext>` where `<sample_id>` is the Bonsai doc's `sample_id` field. The separator (typically `_`) lives inside `mask`, so empty-mask cases like sourmash `<sample>.sig` work without code changes. A `*` anywhere in `mask` enables `fnmatch` wildcard matching. Outputs declared `required: False` (feature/platform-gated tools like skesa, fastqc, kleborate, trimmomatic) are tracked when missing but do not flip a sample's status to FAIL.

Species filtering is permissive: a Bonsai doc matches the requested profile if its `species` (or `metadata.species`) equals either the short form (`saureus`) or the profile-name-with-spaces form (`staphylococcus aureus`). No QC filter is applied — Bonsai is assumed to be the curated set already.

```
jasentool check-backup --profile <PROFILE> --backup-dir <DIR>
                       --db-name <DB> --db-collection <COLLECTION>
                       -o <OUTPUT.csv>
                       [--address <URI>]
```

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `--profile` | Yes | — | JASEN profile name, e.g. `staphylococcus_aureus` |
| `--backup-dir` | Yes | — | Root of the backup storage tree |
| `--db-name` | Yes | — | Bonsai MongoDB database name |
| `--db-collection` | Yes | — | Bonsai MongoDB collection name |
| `-o`/`--output-file` | Yes | — | Summary CSV; per-file missing CSV uses the same stem with `_missing.csv` suffix |
| `--address`/`--uri` | No | `mongodb://localhost:27017/` | Bonsai MongoDB host address |

**Outputs**

- `<output>.csv` — one row per sample: `sample_id, sample_name, profile, required_expected, required_found, optional_expected, optional_found, status` where `status ∈ {PASS, FAIL}`. A sample passes when every required output is found; optional outputs are reported but don't gate the status.
- `<output>_missing.csv` — one row per missing expected file: `sample_id, sample_name, profile, software_name, software_dirname, expected_glob, searched_path, required`.

**Example**

```bash
jasentool check-backup \
  --profile staphylococcus_aureus \
  --backup-dir /backup/jasen \
  --db-name bonsai --db-collection samples \
  --address mongodb://bonsai.host:27017/ \
  -o backup_status.csv
```

## validate-pipelines

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
