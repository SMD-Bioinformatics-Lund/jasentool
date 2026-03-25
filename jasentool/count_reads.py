"""Module for counting reads in FASTQ file(s)"""

import gzip
from jasentool.log import get_logger

logger = get_logger(__name__)

class CountReads:
    """Class for counting reads in FASTQ file(s) without requiring a BAM file."""

    @staticmethod
    def is_gzipped(filepath):
        """Return True if filepath is a gzip-compressed file."""
        with open(filepath, 'rb') as fh:
            return fh.read(2) == b'\x1f\x8b'

    @staticmethod
    def count_reads_in_fastq(filepath, chunk_size=1024 * 1024):
        """Count and return the number of reads in a FASTQ file."""
        open_fn = gzip.open if CountReads.is_gzipped(filepath) else open
        newline_count = 0
        with open_fn(filepath, 'rb') as fh:
            while True:
                chunk = fh.read(chunk_size)
                if not chunk:
                    break
                newline_count += chunk.count(b'\n')
        return newline_count // 4

    def run(self, input_files, sample_id=None):
        """Count reads in one or two FASTQ files and return a summary dict."""
        if len(input_files) == 1:
            n_reads = self.count_reads_in_fastq(input_files[0])
            n_read_pairs = n_reads // 2
        elif len(input_files) == 2:
            r1_reads = self.count_reads_in_fastq(input_files[0])
            r2_reads = self.count_reads_in_fastq(input_files[1])
            assert r1_reads == r2_reads, (
                f"R1 read count ({r1_reads}) does not match R2 read count ({r2_reads})"
            )
            n_reads = r1_reads + r2_reads
            n_read_pairs = r1_reads
        else:
            raise ValueError(f"Expected 1 or 2 input files, got {len(input_files)}")
        logger.info("sample_id=%s n_reads=%d n_read_pairs=%d", sample_id, n_reads, n_read_pairs)
        return {"sample_id": sample_id, "n_reads": n_reads, "n_read_pairs": n_read_pairs}
