"""Module for retrieving qc results"""

import json

import pysam
import numpy as np

from jasentool.log import get_logger

logger = get_logger(__name__)

class QC:
    """Class for retrieving qc results"""
    def __init__(self, args):
        self.results = {}
        self.bam = args.bam
        self.bed = args.bed
        self.sample_id = args.sample_id
        self.cpus = args.cpus
        self.paired = self.is_paired()

    def write_json_result(self, json_result, output_filepath):
        """Write out json file"""
        with open(output_filepath, 'w', encoding="utf-8") as json_file:
            json_file.write(json_result)

    def is_paired(self):
        """Check if reads are paired"""
        with pysam.AlignmentFile(self.bam, "rb") as bam:
            first_read = next(bam.fetch(), None)
            return bool(first_read and first_read.is_paired)

    def get_base_coverage(self):
        """Compute per-base coverage across BED regions using pysam pileup"""
        depths = []
        with pysam.AlignmentFile(self.bam, "rb") as bam:
            with open(self.bed, "r", encoding="utf-8") as bed_fh:
                for line in bed_fh:
                    parts = line.strip().split("\t")
                    chrom, start, end = parts[0], int(parts[1]), int(parts[2])
                    for col in bam.pileup(chrom, start, end, truncate=True,
                                          min_base_quality=0, stepper="nofilter"):
                        depths.append(col.nsegments)
        return depths

    def _collect_flagstats(self):
        """Count total, duplicate, and mapped reads via pysam"""
        num_reads, dup_reads, mapped_reads = 0, 0, 0
        with pysam.AlignmentFile(self.bam, "rb") as bam:
            for read in bam:
                num_reads += 1
                if read.is_duplicate:
                    dup_reads += 1
                if not read.is_unmapped:
                    mapped_reads += 1
        return num_reads, dup_reads, mapped_reads

    def _collect_insert_sizes(self):
        """Compute median insert size and std dev via pysam"""
        insert_sizes = []
        with pysam.AlignmentFile(self.bam, "rb") as bam:
            count = 0
            for read in bam:
                if read.is_read1 and read.is_proper_pair and read.template_length > 0:
                    insert_sizes.append(read.template_length)
                    count += 1
                    if count >= 1_000_000:
                        break
        if insert_sizes:
            arr = np.array(insert_sizes)
            self.results['ins_size'] = str(int(np.median(arr)))
            self.results['ins_size_dev'] = str(round(float(np.std(arr)), 6))

    def run(self):
        """Run QC info extraction"""
        logger.info("Collecting basic stats...")
        num_reads, dup_reads, mapped_reads = self._collect_flagstats()

        if self.paired:
            logger.info("Collect insert sizes...")
            self._collect_insert_sizes()

        thresholds = [1, 10, 30, 100, 250, 500, 1000]

        logger.info("Collecting depth stats...")
        depths = self.get_base_coverage()
        tot_bases = len(depths)
        mean_cov = sum(depths) / tot_bases if tot_bases else 0
        above_pct = {t: 100 * sum(d >= t for d in depths) / tot_bases
                     for t in thresholds} if tot_bases else {t: 0 for t in thresholds}

        self.results['pct_above_x'] = above_pct
        self.results['tot_reads'] = num_reads
        self.results['mapped_reads'] = mapped_reads
        self.results['dup_reads'] = dup_reads
        self.results['dup_pct'] = dup_reads / mapped_reads if mapped_reads else 0
        self.results['sample_id'] = self.sample_id
        self.results['mean_cov'] = mean_cov
        self.results['iqr_median'] = "9999"

        json_result = json.dumps(self.results, indent=4)
        return json_result
