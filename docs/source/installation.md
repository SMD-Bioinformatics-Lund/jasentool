# Installation

## Requirements

- Python >= 3.10
- MongoDB (for subcommands that query/insert data)

## Which path to use

- **Modern Linux / macOS** (glibc >= 2.28: Ubuntu >= 18.04, RHEL/CentOS >= 8, Debian >= 10): `pip install jasentool` works, since current pandas and numpy ship binary wheels for these platforms.
- **Older Linux** (glibc < 2.28): pip can't find matching wheels for current pandas and numpy on Python 3.12, so it falls back to source builds that need GCC 9.3 or newer. Use the **conda from-source** path below instead; conda-forge ships compatible binaries.

## pip

```bash
pip install jasentool
```

## From source

```bash
git clone https://github.com/SMD-Bioinformatics-Lund/jasentool.git
cd jasentool
pip install .
```

## Development install

Install with optional dev dependencies (linting, formatting):

```bash
pip install ".[dev]"
```

## conda

### From PyPI

```bash
conda create -n jasentool python=3.11
conda activate jasentool
pip install jasentool
```

### From source (recommended for older Linux)

```bash
git clone https://github.com/SMD-Bioinformatics-Lund/jasentool.git
cd jasentool
conda env create -f environment.yml
conda activate jasentool
```

`environment.yml` pulls the heavy dependencies (pandas, numpy, matplotlib, biopython, pysam, cyvcf2, openpyxl) from conda-forge, then installs jasentool itself in editable mode (`-e .`).

## Verify installation

```bash
jasentool --help
```
