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

Checks samples in the **Bonsai** MongoDB against the backup storage tree to find ones whose expected JASEN outputs aren't backed up yet. Bonsai is the authoritative list of curated samples, and each document's `sample_id` is the filename prefix used in the backup tree.

The backup tree is laid out as `<backup-dir>/<species_shortname>/<software_dirname>/<file>`. Species shortnames like `saureus` and `ecoli` come from `jasentool/config.py`, which lists the expected outputs per profile as `(software_name, dirname, mask, file_ext, required)` tuples plus a `species_full` long-form name. To change which outputs are checked, edit that file and reinstall the package. `file_ext` can also be a list such as `[".tsv", ".out"]`; a sample's output then counts as backed up if any of the extensions is present, which covers tools whose output extension has changed over time.

Each file is matched as `<sample_id><mask><file_ext>`, where `<sample_id>` is the Bonsai document's `sample_id`. The separator (usually `_`) sits inside `mask`, so empty-mask cases like sourmash's `<sample>.sig` work without a code change. A `*` anywhere in `mask` turns on `fnmatch` wildcard matching. Outputs marked `required: False` are feature- or platform-gated tools such as skesa, fastqc, kleborate and trimmomatic; when missing they're recorded but don't set a sample's status to FAIL.

The MongoDB query is `{"pipeline.analysis_profile": <PROFILE>}`. Thanks to Mongo's array-equality behaviour, this returns every Bonsai document whose `pipeline.analysis_profile` list contains the profile. No QC filter is applied, since Bonsai is already the curated set. Each document's top `species_prediction[0].scientific_name` is checked against the profile's `species_full`; a mismatch is logged as a warning, but the document is still scanned.

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

The primary summary is written to `--output-file` as given. The sibling files reuse the same stem with `_missing.csv` and `_stats.csv` suffixes. So `-o backup.csv` keeps all three named `.csv`, while `-o backup.txt` writes the summary to `backup.txt` but still produces `backup_missing.csv` and `backup_stats.csv`. The content is the same either way; only the suffix changes.

- **`<output-file>`** — per-sample summary. One row per sample, with columns `sample_id, sample_name, lims_id, profile, required_expected, required_found, optional_expected, optional_found, missing_software_output, status`. `status` is `PASS` only when every required output is present, and `FAIL` otherwise (so 25 of 26 still fails). Optional outputs (`required: False` in `jasentool/config.py`) show up in `optional_found` but never affect the status. `missing_software_output` is a semicolon-separated list of the outputs missing for that sample. These are per-output names, not per-tool: `plasmidfinder_meta`, say, rather than `plasmidfinder`.
- **`<stem>_missing.csv`** — one row per missing file. Columns: `sample_id, sample_name, lims_id, profile, software_name, software_dirname, expected_glob, searched_path, required`. `expected_glob` is the filename the matcher looked for (`<sample_id><mask><file_ext>`) and `searched_path` is the directory it looked in. To confirm that one tool is missing across the board, group by `software_name`.
- **`<stem>_stats.csv`** — one row per declared output. Columns: `software_name, dirname, mask, file_ext, required, n_missing, n_found, total_samples, missing_pct`. Sorted by `n_missing`, worst first. The top ten are also printed to the log (`Top N outputs by missing count: ...`), so you can spot config drift without opening the CSV.
- **`<stem>_review.csv`** — Bonsai-side sample quirks, one row per `(sample, reason)`. Columns: `sample_id, sample_name, lims_id, profile, reason`. `reason` is one of `name_equals_id` (the `sample_name` equals the `sample_id`, usually because the readable name was never set on import), `duplicate_sample_id` (the `sample_id` appears more than once in the queried set), or `duplicate_sample_name` (the `sample_name` appears more than once, a possible duplicate upload). Always written; header-only when there are no quirks.
- **`<stem>_masked_assemblies.csv`** — backed-up masked FASTA assemblies, limited to samples where `sample_name != sample_id`. One row per `<sample_id>_mask.fasta` found in `<backup-dir>/<species>/mask/`. These are the outputs of JASEN's `mask_polymorph_assembly` step and the exact input chewBBACA originally consumed. Columns: `sample_id, sample_name, lims_id, profile, masked_assembly_path`. Samples flagged `name_equals_id` in `<stem>_review.csv` are excluded. Feed this CSV to `jasentool rerun-chewbbaca` when re-running chewBBACA after a schema or version update.
- **`<stem>_group_orphans.csv`** — a Bonsai data-integrity check, one row per `(group, sample_id)` where the `sample_id` is listed in some `sample_group.included_samples` but doesn't exist in the `sample` collection. Columns: `group_id, group_name, sample_id`. This is profile-independent: it queries the full `sample` and `sample_group` collections regardless of `--profile`. Always written; header-only when every group reference resolves.
- **`<stem>_orphans.csv`** — files in the backup tree that don't match any expected entry. Only written with `--check-orphans`. One row per orphan: `filepath, species, software_dirname, filename`. Common causes: the filename starts with a `sample_id` no longer in Bonsai (the sample was deleted but its files remain); it starts with a known `sample_id` but the suffix doesn't match (`jasentool/config.py` is behind what the pipeline now writes); or it doesn't look like a `sample_id` at all (`README`, `.DS_Store`, a half-written `.tmp`, a manual upload). Files ending in `_versions.yml` are matched by `sample_id` prefix rather than exact name, since they're JASEN's per-process metadata (`<sample>_<process_path>_versions.yml`): if the prefix matches a known `sample_id` the file is skipped, otherwise it's flagged like any other orphan.

Log records go to **stdout**, not stderr, so a plain redirect captures them: `jasentool check-backup ... > backup_run.log`. The tqdm progress bar still writes to stderr (it doesn't go through the logger), so the captured file stays free of progress-bar noise.

**Example**

```bash
jasentool check-backup \
  --profile staphylococcus_aureus \
  --backup-dir /backup/jasen \
  --db-name bonsai --db-collection samples \
  --address mongodb://bonsai.host:27017/ \
  -o backup_status.csv
```

## rebuild-manifests

Rebuilds `create-yaml` manifests (`<sample_id>_bonsai.yaml`) from the backup storage tree. This is handy after a `create-yaml` format change, when the backed-up manifests are still in their old format.

There are two ways to choose which samples to rebuild:

- **Bonsai-driven (default)** queries the Bonsai MongoDB for every sample whose `pipeline.analysis_profile` contains the profile, the same query `check-backup` uses. It takes each sample's `sample_name` and `lims_id` from Bonsai, and its `groups` from a reverse lookup of `sample_group.included_samples`.
- **Tree-driven (`--no-bonsai`)** skips Bonsai and finds samples by scanning the backup tree. Every filename under the profile's output dirs that ends in a declared `<mask><file_ext>` suffix contributes its prefix as a `sample_id`, taken as a union across all outputs, so a sample turns up as long as one of its files is there. Stripping a known suffix recovers the `sample_id` even when it contains underscores. Wildcard-mask outputs and `_versions.yml` files are ignored. Nothing connects to MongoDB, so `--db-name`/`--db-collection` aren't needed. Bonsai's metadata isn't available in this mode, so `sample_name` falls back to `sample_id` and `lims_id`/`groups` are left unset.

Either way, the analysis-result files are located with the same per-profile output declarations `check-backup` uses (`jasentool/config.py`), and a `software_name` → `create-yaml` field mapping (`CREATE_YAML_FIELD_MAP`, also in `jasentool/config.py`) says which flag each file feeds. Outputs with no matching `create-yaml` field are skipped: `resfinder_meta`, `mask_polymorph`, `format_jasen`, and `post_align_qc` (which has no dedicated `create-yaml` flag). When a profile has more than one possible IGV `vcf` source (TB's `tbprofiler_vcf`/`snippy_vcf` versus non-TB's `freebayes`), the first match in `CREATE_YAML_VCF_PRIORITY` order wins.

**Run metadata (`nextflow_run_info` and `lims_id`).** JASEN's `save_analysis_metadata` step writes `<backup-dir>/<species>/analysis_metadata/<sample_id>_analysis_meta.json`. It holds the run info (`pipeline`, `version`, `commit`, `release_life_cycle`, `command`, `analysis_profile`, `sequencing_run`, and so on) as well as `lims_id` and `sample_name`. rebuild-manifests points the manifest's `nextflow_run_info` at this file and reads `lims_id` from it (and `sample_name` in `--no-bonsai` mode). bonsai-prp requires all of these. When Bonsai has a `lims_id` or `sample_name`, that value wins and the metadata only fills the gap. If the file is missing, the sample is still written, but a warning notes that the manifest will lack `nextflow_run_info` and `lims_id`. This is the same file `format-cdm` parses, via `jasentool/cdm/loader.py`.

JASEN writes one `_versions.yml` per process, spread across each tool's own output directory (`<backup-dir>/<species>/<dirname>/<sample_id>_<process_path>_versions.yml`). For each sample, every matching file is merged into `<output-dir>/<sample_id>_versions.yml` and passed to `create-yaml --versions`, so `software_version` ends up in the rebuilt manifest. These files are read defensively, since they're pipeline outputs that sometimes contain junk (a leaked `END_VERSIONS` heredoc terminator, or a stray bare version line). Any non-blank line without a colon is dropped before parsing, and a file that still won't parse is logged and skipped rather than aborting the run.

**Filling missing versions (`--versions-fallback`).** Some tools have no usable version in the tree: either no `_versions.yml` was written (chewbbaca, for example), or the file records only a database version (`virulencefinder_db`) and not the tool version. Pass `--versions-fallback <file>`, a flat `software: version` YAML, to fill those gaps:

```yaml
chewbbaca: '3.3.2'
virulencefinder: '2.0.4'
amrfinderplus: '3.11.11'
```

The tree always wins: a fallback value is used only when a tool the sample has an output file for has no version from the tree. Keys are the software name as it appears *inside* a versions.yml (what `create-yaml` looks up), not the container image name, so `amrfinderplus` rather than `ncbi-amrfinderplus`, `bracken` for kraken/bracken, and `tb-profiler`. Only versions relevant to the sample's outputs are applied; other entries in the file are ignored. Each fill is logged (`<sample_id>: filled N version(s) from fallback: ...`). A ready-made file for the current pipeline release ships at `versions_fallback.yml` in the repo root.

```
jasentool rebuild-manifests --profile <PROFILE> --backup-dir <DIR>
                            -o <OUTPUT_DIR>
                            (--db-name <DB> --db-collection <COLLECTION> | --no-bonsai)
                            [--address <URI>] [--db-collection-groups <COLLECTION>]
                            [--sample-id <ID>] [--versions-fallback <FILE>]
```

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `--profile` | Yes | — | JASEN profile name, e.g. `staphylococcus_aureus` |
| `--backup-dir` | Yes | — | Root of the backup storage tree |
| `-o`/`--output-dir` | Yes | — | Directory to write `<sample_id>_bonsai.yaml` and `<sample_id>_versions.yml` |
| `--no-bonsai` | No | False | Discover samples by scanning the backup tree instead of querying Bonsai. `sample_name` falls back to `sample_id`; `lims_id` and `groups` are left unset |
| `--db-name` | Unless `--no-bonsai` | — | Bonsai MongoDB database name |
| `--db-collection` | Unless `--no-bonsai` | — | Bonsai MongoDB collection name (samples) |
| `--db-collection-groups` | No | `sample_group` | Bonsai MongoDB collection holding `sample_group` docs (used to resolve each sample's `groups`) |
| `--address`/`--uri` | No | `mongodb://localhost:27017/` | Bonsai MongoDB host address |
| `--sample-id` | No | — | Rebuild only this one sample. Handy for a test run before doing everything. Works in both modes |
| `--versions-fallback` | No | — | Flat `software: version` YAML used to fill a version the backup tree lacks for a tool (the tree always wins) |

**Outputs** (per sample, in `--output-dir`)

- **`<sample_id>_versions.yml`** — the merged per-process versions file, including any `--versions-fallback` fills. Omitted only when neither the tree nor the fallback produced a version for the sample.
- **`<sample_id>_bonsai.yaml`** — the rebuilt manifest. Written even when some or all analysis-result files are missing; the absent fields are just left out, the same way `create-yaml` handles missing inputs.

**Examples**

```bash
# Bonsai-driven
jasentool rebuild-manifests \
  --profile staphylococcus_aureus \
  --backup-dir /backup/jasen \
  --db-name bonsai --db-collection samples \
  --address mongodb://bonsai.host:27017/ \
  -o rebuilt_manifests/

# Tree-driven, no MongoDB needed
jasentool rebuild-manifests \
  --profile staphylococcus_aureus \
  --backup-dir /backup/jasen \
  --no-bonsai \
  -o rebuilt_manifests/
```

## compare-distances

Builds pairwise cgMLST distance matrices for **two** chewBBACA allele-call tables and writes their element-wise difference. Use it to measure how sample-to-sample distances shift between two chewBBACA runs, for example before and after re-running chewBBACA on masked assemblies (see `rerun-chewbbaca`), or after a schema or version change.

Each input is a chewBBACA table: a header row, then one sample per row with `sample_id` in the first column and the per-locus allele calls after it. The header is required, and the command errors if the first row isn't one. Either style is accepted: newer output leads with `FILE` (`FILE<tab>locus...`), older output with `#Name` (`#Name<tab>ST<tab>locus...`), and the two files may differ here. The header is used to drop the leading `ST` column from older AlleleCall output so only per-locus calls are compared. The delimiter is detected automatically (tab, falling back to comma). Loci are compared by position within each file, so the two files don't have to name their loci the same way, but they should share the same sample names.

For each file, a sample × sample matrix is built where each cell is the number of loci at which the two samples' calls **differ** (matching loci score 0, mismatching loci score 1). Loci where either call is missing or an error (`-`, `INF`, `LNF`, `PLOT3`, `PLOT5`, `NIPH`, `ASM`, and so on) are skipped rather than counted as a mismatch. Distances come from [`cgmlst-dists`](https://github.com/tseemann/cgmlst-dists): each file is first written out sorted by sample id with the `ST` column dropped (`<stem>_clean.tsv`), then run through `cgmlst-dists -x 2000`. If the binary isn't found (set its path with `--cgmlst-dists-bin`), it falls back to the pure-Python method in `jasentool/matrix.py`. The `-x 2000` matters: cgmlst-dists caps distances at its `-x` value (default 999) and returns early once it's reached, which would pile every larger distance onto 999; raising the cap above the usual locus count keeps the real spread. The difference matrix is `matrix1 - matrix2` over the samples in both files.

**Missing-data (`-`) control.** Because `-` loci are skipped, a file with more missing data gives systematically smaller distances, which skews the difference. A few outputs help you tell missing data apart from genuine allele changes:

- a per-sample **missing-loci** count (`n_missing` for each file plus their `delta`). This is usually the quickest way to see whether the version change moved missing data around and which samples drive it. A call counts as missing unless it's an integer allele. chewBBACA inferred alleles (`INF-<n>`) have the `INF-` prefix stripped and count as allele `<n>`, so `-`, `LNF`, `PLOT3`, `NIPH` and the like are missing, but `INF-123` is not.
- a **dash_change** matrix: for each pair, the number of loci comparable in exactly one of the two files (a `-` appeared or disappeared between versions). Symmetric and non-negative.
- an **unexplained** matrix: `max(0, |distance1 - distance2| - dash_change)`. Read it as a lower bound on real allele-call differences. Where it's `0`, the distance difference is fully explained by missing data; where it's positive, at least that many loci genuinely changed.

`dash_change` and `unexplained` use the same definition of missing (any non-integer call except a stripped `INF-<n>`) and compare the files locus by locus, so both files must list the **same loci in the same column order** (the same cgMLST scheme). If the locus counts differ, these two are skipped with a warning.

Samples present in only one of the two files are written to a missing-samples report and left out of the difference matrices, which still run over the shared samples.

```
jasentool compare-distances -i <FILE1.tsv> <FILE2.tsv> -o <OUTPUT_DIR>
                            [--mlst <SAMPLE_ST.csv>] [--cgmlst-dists-bin <PATH>]
```

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `-i`/`--input` | Yes | — | The two chewBBACA cgMLST allele-call TSVs, listed one after the other |
| `-o`/`--output-dir` | Yes | — | Output directory for the matrices, plots and reports (created if missing) |
| `--mlst` | No | — | `sample_name,mlst_st` CSV/TSV; enables the missing-loci-vs-ST plot |
| `--cgmlst-dists-bin` | No | `cgmlst-dists` | Path/name of the cgmlst-dists executable (Python fallback if absent) |
| `-v`/`--verbose` | No | off | Verbose logging and write the plots' underlying point tables (`*_points.tsv`) for manual checking |

> `cgmlst-dists` is a separate bioconda tool, not a Python dependency. Install it through the conda `environment.yml` (or however you prefer) to use it; without it, the Python fallback runs.

**Outputs**

Every matrix has its rows and columns sorted by sample id, so the two distance matrices and the diff share the same stable ordering no matter what order the inputs were in. File names come from the input basenames (`<stem>` is the filename without extension; if both stems are the same, `_1` and `_2` are appended).

- **`<stem1>_distance_matrix.tsv`** — sample × sample mismatch-count (distance) matrix for the first file. Symmetric; diagonal is 0.
- **`<stem2>_distance_matrix.tsv`** — the same for the second file.
- **`<stem1>_vs_<stem2>_diff_matrix.tsv`** — element-wise `matrix1 - matrix2`, restricted to the samples present in both files (samples unique to one file are excluded).
- **`<stem1>_vs_<stem2>_abs_diff_matrix.tsv`** — `|matrix1 - matrix2|`.
- **`<stem1>_vs_<stem2>_dash_change_matrix.tsv`** — per pair, loci comparable in exactly one of the two files (a `-` appeared/disappeared between versions). Symmetric, non-negative. Omitted if the files' loci counts differ.
- **`<stem1>_vs_<stem2>_unexplained_matrix.tsv`** — `max(0, |diff| - dash_change)`; a lower bound on differences not attributable to missing data. Omitted if the files' loci counts differ.
- **`<stem1>_vs_<stem2>_missing_loci_per_sample.tsv`** — per-sample missing-loci counts: `sample_id, n_missing_<stem1>, n_missing_<stem2>, delta` (delta blank for samples absent from a file). Missing = any non-integer call except stripped `INF-<n>` inferred alleles.
- **`<stem1>_vs_<stem2>_missing_samples.tsv`** — samples present in one file but not the other, hence excluded from the diff. Columns: `sample_id, present_in, missing_from` (file basenames). Always written; header-only when both files share all samples.
- **`<stem1>_clean.tsv`** / **`<stem2>_clean.tsv`** — each input sorted by sample id with the `ST` column dropped; these are what `cgmlst-dists` is run on.
- **`<stem1>_vs_<stem2>_distance_scatter.png`** — scatter of every shared sample-pair's distance in file 1 (x) vs file 2 (y), with a `y=x` identity line.
- **`<stem1>_vs_<stem2>_bland_altman.png`** — Bland–Altman of the pairwise distances: mean of the two distances (x) vs their difference (y), with the mean difference and ±1.96·SD limits.
- **`<stem1>_vs_<stem2>_missing_vs_st.png`** — *only with `--mlst`*. Per-sample missing-loci counts grouped by MLST ST, with one box+points per ST for each file, to spot STs carrying more missing data.
- **`<stem1>_vs_<stem2>_distance_points.tsv`** — *only with `-v`*. One row per sample pair behind the scatter/Bland–Altman: `sample_a, sample_b, <stem1>_distance, <stem2>_distance, mean, diff`.
- **`<stem1>_vs_<stem2>_missing_vs_st_points.tsv`** — *only with `-v` and `--mlst`*. The points behind the ST plot: `sample, ST, version, n_missing`.

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
