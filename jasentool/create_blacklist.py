"""Module for creating a minority variant blacklist from a set of BAM files"""

import re
import subprocess
from pathlib import Path

from jasentool.minority_report import MinorityReport
from jasentool.log import get_logger

logger = get_logger(__name__)


class CreateBlacklist:
    """Create a minority variant blacklist by aggregating per-sample minority distributions."""

    def __init__(self, samtools='samtools'):
        self.samtools = samtools
        self.reporter = MinorityReport()

    def _get_bam_files(self, bam_input_file, input_dir):
        """Return a list of BAM paths from a text file of paths or a directory."""
        if bam_input_file:
            bam_files = []
            with open(bam_input_file, 'r', encoding='utf-8') as fh:
                for line in fh:
                    path = line.strip()
                    if path:
                        bam_files.append(Path(path))
            return bam_files
        if input_dir:
            return sorted(Path(input_dir).glob('*.bam'))
        return []

    def _run_mpileup(self, bam_path, out_mpileup, bed_file=None):
        """Run samtools mpileup on a BAM file."""
        cmd = [self.samtools, 'mpileup', str(bam_path), '-o', str(out_mpileup)]
        if bed_file:
            cmd += ['-l', str(bed_file)]
        subprocess.check_call(cmd)

    def run(self, bam_input_file, input_dir, output_dir, output_file,
            bed_file=None, min_freq=0.05, min_count=5, sample_pattern='.*'):
        """
        For each BAM file: run mpileup and compute minority base distribution.
        Aggregate .withpos files across samples to produce a blacklist TSV.

        Only samples whose stem matches `sample_pattern` contribute to the
        blacklist aggregation (default: all samples).
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        bam_files = self._get_bam_files(bam_input_file, input_dir)
        if not bam_files:
            raise FileNotFoundError('No BAM files found in the specified input.')

        pattern = re.compile(sample_pattern)
        withpos_files = []

        for bam in bam_files:
            sample_name = bam.stem
            mpileup_path = output_dir / f"{sample_name}.mpileup"
            dist_path = output_dir / f"{sample_name}_minority_dist"

            logger.info("Running mpileup for %s", sample_name)
            self._run_mpileup(bam, mpileup_path, bed_file)

            logger.info("Computing minority distribution for %s", sample_name)
            _, withpos_path = self.reporter.minority_base_distribution(mpileup_path, dist_path)

            if pattern.search(sample_name):
                withpos_files.append(withpos_path)
            else:
                logger.debug("Skipping %s (does not match sample_pattern)", sample_name)

        pos_counts = {}
        for withpos in withpos_files:
            with open(withpos, 'r', encoding='utf-8') as fh:
                for line in fh:
                    parts = line.strip().split('\t')
                    if len(parts) < 2:
                        continue
                    pos, freq = parts[0], float(parts[1])
                    if freq > min_freq:
                        pos_counts[pos] = pos_counts.get(pos, 0) + 1

        with open(output_file, 'w', encoding='utf-8') as fout:
            for pos, count in pos_counts.items():
                if count >= min_count:
                    fout.write(f"{pos}\t{count}\n")

        logger.info("Wrote blacklist to %s", output_file)
