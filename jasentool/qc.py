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
        """Compute per-base coverage; BED-region or genome-wide depending on self.bed"""
        with pysam.AlignmentFile(self.bam, "rb") as bam:
            if self.bed is not None:
                depths = []
                with open(self.bed, "r", encoding="utf-8") as bed_fh:
                    for line in bed_fh:
                        parts = line.strip().split("\t")
                        chrom, start, end = parts[0], int(parts[1]), int(parts[2])
                        region_cov = np.zeros(end - start, dtype=np.int32)
                        for col in bam.pileup(chrom, start, end, truncate=True,
                                              min_base_quality=0, stepper="nofilter"):
                            region_cov[col.reference_pos - start] = col.nsegments
                        depths.extend(region_cov.tolist())
                return np.array(depths, dtype=np.int32)
            else:
                refs = list(bam.header.references)
                ref_lengths = [bam.header.get_reference_length(r) for r in refs]
                total_bases = sum(ref_lengths)
                coverage = np.zeros(total_bases, dtype=np.int32)
                offsets, offset = {}, 0
                for ref, length in zip(refs, ref_lengths):
                    offsets[ref] = offset
                    offset += length
                for col in bam.pileup(min_base_quality=0, stepper="nofilter"):
                    coverage[offsets[col.reference_name] + col.reference_pos] = col.nsegments
                return coverage

    def _parse_flagstat(self):
        """Parse pysam.flagstat() output to extract read counts"""
        stats = {'n_reads': 0, 'n_dup_reads': 0, 'n_mapped_reads': 0, 'n_read_pairs': 0}
        for line in pysam.flagstat(self.bam).splitlines():
            count = int(line.split(' + ')[0])
            if 'in total' in line:
                stats['n_reads'] = count
            elif 'primary duplicates' in line:
                stats['n_dup_reads'] = count
            elif 'primary mapped' in line:
                stats['n_mapped_reads'] = count
            elif 'paired in sequencing' in line:
                stats['n_read_pairs'] = count
        return stats

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
            self.results['ins_size'] = round(float(np.median(arr)), 6)
            self.results['ins_size_dev'] = round(float(np.std(arr)), 6)

    def run(self):
        """Run QC info extraction"""
        logger.info("Collecting basic stats...")
        fs = self._parse_flagstat()

        if self.paired:
            logger.info("Collect insert sizes...")
            self._collect_insert_sizes()

        thresholds = [1, 10, 30, 100, 250, 500, 1000]

        logger.info("Collecting depth stats...")
        depths = self.get_base_coverage()
        tot_bases = len(depths)

        if tot_bases:
            mean_cov = float(np.mean(depths))
            q1 = float(np.percentile(depths, 25))
            median_cov = float(np.median(depths))
            q3 = float(np.percentile(depths, 75))
            coverage_uniformity = (q3 - q1) / median_cov if median_cov else 0.0
            above_pct = {t: round(100 * float(np.sum(depths >= t)) / tot_bases, 6)
                         for t in thresholds}
        else:
            mean_cov = 0.0
            q1 = 0.0
            median_cov = 0.0
            q3 = 0.0
            coverage_uniformity = 0.0
            above_pct = {t: 0.0 for t in thresholds}

        self.results['pct_above_x'] = above_pct
        self.results['mean_cov'] = mean_cov
        self.results['coverage_uniformity'] = coverage_uniformity
        self.results['quartile1'] = q1
        self.results['median_cov'] = median_cov
        self.results['quartile3'] = q3
        self.results['n_reads'] = fs['n_reads']
        self.results['n_mapped_reads'] = fs['n_mapped_reads']
        self.results['n_read_pairs'] = fs['n_read_pairs']
        self.results['n_dup_reads'] = fs['n_dup_reads']
        self.results['dup_pct'] = fs['n_dup_reads'] / fs['n_mapped_reads'] if fs['n_mapped_reads'] else 0.0
        self.results['sample_id'] = self.sample_id

        json_result = json.dumps(self.results, indent=4)
        return json_result
