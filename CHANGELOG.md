# Clinical-Genomics-Lund/jasentool: Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [v0.2.0]

### Added

 - Added tb validation notebook
 - Added output csv for failed validation samples
 - Added differential matrix for validation
 - Added saureus validation notebook
 - Added `--generate_matrix` argument to cli
 - Added `alter_sample_id` filter
 - Added summed differential matrix
 - Added mean coverage plot
 - Added jitter to mean coverage boxplot

### Fixed

 - Fixed `pyproject.toml` setuptools bug
 - Fixed cgmlst comparison and plots
 - Fixed `fix` subarg
 - Fixed TN/TP/FN/FP plots

### Changed

 - Changed id format for fix and missing
 - Changed matrix to boxplot, jitter, and annotate
