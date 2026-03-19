# Site-specific hooks

Built specifically for Clinical Genomics Lund's BJORN system.

## reformat-csv

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
