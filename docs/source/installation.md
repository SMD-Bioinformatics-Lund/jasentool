# Installation

## Requirements

- Python >= 3.10
- MongoDB (for subcommands that query/insert data)

## Which path to use

- **Modern Linux / macOS** (glibc >= 2.28, i.e. Ubuntu >= 18.04, RHEL/CentOS >= 8, Debian >= 10): plain `pip install jasentool` works — current pandas / numpy ship binary wheels for these platforms.
- **Older Linux** (glibc < 2.28): pip will not find matching binary wheels for current pandas / numpy on Python 3.12 and will fall back to source builds that require GCC >= 9.3. Use the **conda from-source** path below instead — conda-forge ships its own compatible binaries.

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

`environment.yml` installs every binary-heavy dependency (pandas, numpy, matplotlib, biopython, pysam, cyvcf2, openpyxl) from conda-forge and then performs an editable (`-e .`) pip install of jasentool itself.

## Verify installation

```bash
jasentool --help
```
