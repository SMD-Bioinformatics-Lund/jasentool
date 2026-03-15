# Installation

## Requirements

- Python >= 3.10
- MongoDB (for subcommands that query/insert data)

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

```bash
conda create -n jasentool python=3.11
conda activate jasentool
pip install jasentool
```

## Verify installation

```bash
jasentool --help
```
