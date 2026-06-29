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

Backup tree layout: `<backup-dir>/<species_shortname>/<software_dirname>/<file>`. Species shortnames (e.g. `saureus`, `ecoli`) come from `jasentool/config.py` — that module holds the per-profile schedule of expected outputs as `(software_name, dirname, mask, file_ext, required)` tuples plus a `species_full` long-form name. Edit it and reinstall the package to change which outputs are checked. `file_ext` may also be a list, e.g. `[".tsv", ".out"]`, in which case a sample's output counts as backed up if **any** listed extension is present (used for tools whose output extension has changed over time).

Files are matched per sample as `<sample_id><mask><file_ext>` where `<sample_id>` is the Bonsai doc's `sample_id` field. The separator (typically `_`) lives inside `mask`, so empty-mask cases like sourmash `<sample>.sig` work without code changes. A `*` anywhere in `mask` enables `fnmatch` wildcard matching. Outputs declared `required: False` (feature/platform-gated tools like skesa, fastqc, kleborate, trimmomatic) are tracked when missing but do not flip a sample's status to FAIL.

Server-side filter: `{"pipeline.analysis_profile": <PROFILE>}` — Mongo's array-equality semantics return every Bonsai doc whose `pipeline.analysis_profile` list contains the requested profile. No QC filter is applied (Bonsai is assumed to be the curated set already). Each returned doc's top `species_prediction[0].scientific_name` is compared against the profile's `species_full` and a `warning` is logged on mismatch (the doc is still scanned).

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
| `--db-collection` | Yes | — | Bonsai MongoDB collection name (samples) |
| `--db-collection-groups` | No | `sample_group` | Bonsai MongoDB collection holding `sample_group` docs (used for the group-orphans check) |
| `-o`/`--output-file` | Yes | — | Summary CSV; per-file missing CSV uses the same stem with `_missing.csv` suffix |
| `--address`/`--uri` | No | `mongodb://localhost:27017/` | Bonsai MongoDB host address |
| `--check-orphans` | No | False | After scanning, also list files in the backup tree that don't match any expected `<sample_id><mask><file_ext>`; emits `<stem>_orphans.csv` |

**Outputs**

`--output-file` is taken verbatim for the primary summary; the two sibling files use the same stem with `_missing.csv` and `_stats.csv` suffixes. Pass `-o backup.csv` to keep all three files `.csv`-named — passing `-o backup.txt` writes CSV content to `backup.txt` while still producing `backup_missing.csv` and `backup_stats.csv` (the content is identical either way; only the suffix differs).

- **`<output-file>`** — *per-sample summary*. One row per sample with columns `sample_id, sample_name, lims_id, profile, required_expected, required_found, optional_expected, optional_found, missing_software_output, status`. `status` is `PASS` when every required output is found in the backup tree and `FAIL` otherwise (so 25-of-26 still counts as FAIL). Optional outputs (`required: False` in `jasentool/config.py`) are reported via `optional_found` but never gate the status. `missing_software_output` is a semi-colon-joined list of every output name (per-output identifier, not per-tool — e.g. `plasmidfinder_meta`, not `plasmidfinder`) that was absent for that sample.
- **`<stem>_missing.csv`** — *per-missing-file detail*. One row per `(sample, missing-output)` pair: `sample_id, sample_name, lims_id, profile, software_name, software_dirname, expected_glob, searched_path, required`. `expected_glob` is the exact filename the matcher looked for (`<sample_id><mask><file_ext>`), and `searched_path` is the directory it looked in. Useful when one specific software is missing system-wide — group by `software_name` to confirm.
- **`<stem>_stats.csv`** — *per-output aggregate*. One row per declared output: `software_name, dirname, mask, file_ext, required, n_missing, n_found, total_samples, missing_pct`. Sorted by `n_missing` descending so the worst offenders are at the top. The top ten are also echoed to the log line `Top N outputs by missing count: ...` so you can spot config drift without opening the CSV.
- **`<stem>_review.csv`** — *Bonsai-side sample quirks*. One row per `(sample, reason)`: `sample_id, sample_name, lims_id, profile, reason`. `reason` is one of `name_equals_id` (the sample's `sample_name` field equals its `sample_id` — usually means the human-readable name was never set on import), `duplicate_sample_id` (this `sample_id` appears more than once in the queried set — data-integrity flag), or `duplicate_sample_name` (this `sample_name` appears more than once — possible duplicate uploads). Always emitted; empty (header-only) when no quirks are detected.
- **`<stem>_masked_assemblies.csv`** — *backed-up masked FASTA assemblies, filtered to `sample_name != sample_id`*. One row per existing `<sample_id>_mask.fasta` in `<backup-dir>/<species>/mask/` — these are the outputs of JASEN's `mask_polymorph_assembly` step and the exact input chewBBACA originally consumed. Columns: `sample_id, sample_name, lims_id, profile, masked_assembly_path`. Samples flagged as `name_equals_id` in `<stem>_review.csv` are excluded. Use this CSV as the input manifest for the companion `jasentool rerun-chewbbaca` subcommand when re-running chewBBACA after a schema or version update.
- **`<stem>_group_orphans.csv`** — *Bonsai-side data-integrity check*. One row per `(group, sample_id)` where the `sample_id` appears in some `sample_group.included_samples` list but doesn't exist in the `sample` collection. Columns: `group_id, group_name, sample_id`. Profile-independent — queries the full `sample` and `sample_group` collections regardless of `--profile`. Always emitted; empty (header-only) when every group reference resolves.
- **`<stem>_orphans.csv`** — *files in the backup tree without a matching expected entry*. Only written when `--check-orphans` is passed. One row per orphan: `filepath, species, software_dirname, filename`. Typical causes: filename starts with a `sample_id` no longer in Bonsai (sample deleted but files remain); filename starts with a recognised `sample_id` but the suffix doesn't match (`jasentool/config.py` is out of date with what the pipeline now writes); filename doesn't look like any `sample_id` (`README`, `.DS_Store`, half-written `.tmp`, manual upload). Files ending in `_versions.yml` are checked by sample_id prefix-match instead of literal-name match — those are JASEN's per-process metadata (`<sample>_<process_path>_versions.yml`). If the prefix matches a known Bonsai `sample_id`, the file is silently skipped; if it doesn't (e.g. the sample was deleted from Bonsai but the file lingers), it's flagged like any other orphan.

Log records are written to **stdout** (not stderr), so a plain shell redirect captures them: `jasentool check-backup ... > backup_run.log`. Note that the tqdm progress bar still writes to stderr (tqdm doesn't go through the logger) so the captured file stays free of progress-bar carriage-return noise.

**Example**

```bash
jasentool check-backup \
  --profile staphylococcus_aureus \
  --backup-dir /backup/jasen \
  --db-name bonsai --db-collection samples \
  --address mongodb://bonsai.host:27017/ \
  -o backup_status.csv
```

## compare-distances

Builds pairwise cgMLST distance matrices for **two** chewBBACA allele-call tables and writes their element-wise difference. Useful for quantifying how sample-to-sample distances shift between two chewBBACA runs — e.g. before vs after re-running chewBBACA on masked assemblies (see `rerun-chewbbaca`) or after a schema/version change.

Each input is a chewBBACA table: a required header row, then one sample per row with `sample_id` in the first column and the per-locus allele calls in the remaining columns. The header is required (the command errors if the first row isn't a header) and may use either style — newer output leads with `FILE` (`FILE<tab>locus...`), older output with `#Name` (`#Name<tab>ST<tab>locus...`). The header is used to drop the leading `ST` column (older AlleleCall output) so only per-locus calls are compared. The delimiter is auto-detected (tab, falling back to comma). Loci are compared positionally within each file, so the two files need not share locus naming, but they should share the same sample names. The two files may use different header styles.

For each file a sample × sample matrix is built where a cell is the number of loci at which the two samples' calls **differ** (matching loci score 0, mismatching loci `+1`). Comparison reuses `jasentool/matrix.py`: calls are compared as integers, and loci where either call is missing/error (`-`, `INF`, `LNF`, `PLOT3`, `PLOT5`, `NIPH`, `ASM`, ...) are skipped rather than counted as a mismatch. The difference matrix is `matrix1 - matrix2` over the samples shared by both files.

**Missing-data (`-`) control.** Because `-` loci are skipped, a file with more missing data yields systematically smaller distances, which skews the raw difference. To control for this, a per-file signed `-` matrix is also built: for each pair it counts loci where **only the row sample** is `-` (`+1`) minus loci where **only the column sample** is `-` (`-1`); loci where **both** or **neither** are `-` score `0`. This matrix is therefore skew-symmetric (`cell[A][B] == -cell[B][A]`) and captures the imbalance in missing data between the two samples. Their difference (`dash1 - dash2`) is subtracted from the distance difference to give a **corrected difference matrix** (`(distance1 - distance2) - (dash1 - dash2)`); because the `-` matrices are signed, the corrected matrix is not symmetric. Only the literal `-` code is counted here (other null/error codes are not).

Samples present in only one of the two files are identified and written to a missing-samples report; they are excluded from the difference matrices, which still run over the shared samples.

```
jasentool compare-distances -i <FILE1.tsv> <FILE2.tsv> -o <OUTPUT_DIR>
```

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `-i`/`--input` | Yes | — | The two chewBBACA cgMLST allele-call TSVs, listed one after the other |
| `-o`/`--output-dir` | Yes | — | Output directory for the two distance matrices and their difference (created if missing) |

**Outputs**

All matrices have their rows and columns sorted by sample id (so the two distance matrices and the diff share a stable, readable ordering regardless of input row order). File names derive from the input basenames (`<stem>` = filename without extension; if both stems match, `_1`/`_2` are appended).

- **`<stem1>_distance_matrix.tsv`** — sample × sample mismatch-count (distance) matrix for the first file. Symmetric; diagonal is 0.
- **`<stem2>_distance_matrix.tsv`** — the same for the second file.
- **`<stem1>_vs_<stem2>_diff_matrix.tsv`** — element-wise `matrix1 - matrix2`, restricted to the samples present in both files (samples unique to one file are excluded).
- **`<stem1>_dash_matrix.tsv`** / **`<stem2>_dash_matrix.tsv`** — per-file signed `-` matrices (per pair: loci where only the row sample is `-` minus loci where only the column sample is `-`; both/neither score 0). Skew-symmetric.
- **`<stem1>_vs_<stem2>_dash_diff_matrix.tsv`** — element-wise `dash1 - dash2` over shared samples.
- **`<stem1>_vs_<stem2>_corrected_diff_matrix.tsv`** — the distance difference with the `-` differential subtracted: `(matrix1 - matrix2) - (dash1 - dash2)`.
- **`<stem1>_vs_<stem2>_missing_samples.tsv`** — samples present in one file but not the other, hence excluded from the diff. Columns: `sample_id, present_in, missing_from` (file basenames). Always written; header-only when both files share all samples.

**Example**

```bash
jasentool compare-distances \
  -i original_chewbbaca.tsv rerun_chewbbaca.tsv \
  -o distance_comparison/
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
