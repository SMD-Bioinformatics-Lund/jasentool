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
