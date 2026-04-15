"""Module for minority base distribution analysis from mpileup data"""

import re
import gzip
from pathlib import Path

from jasentool.log import get_logger

logger = get_logger(__name__)


def read_blacklist(filepath):
    """Read a blacklist TSV file and return a set of blacklisted positions."""
    blacklisted = set()
    with open(filepath, 'r', encoding='utf-8') as fh:
        for line in fh:
            data = line.strip().split('\t')
            if data:
                blacklisted.add(data[0])
    return blacklisted


def parse_pile(reads, ref):
    """Parse a mpileup read column and return per-base counts."""
    counts = {'A': 0, 'T': 0, 'C': 0, 'G': 0, 'N': 0}
    i = 0
    while i < len(reads):
        if reads[i] in "ACGTNacgtn":
            counts[reads[i].upper()] += 1
            i += 1
        elif reads[i] in ',.':
            counts[ref.upper()] += 1
            i += 1
        elif reads[i] in '$*':
            i += 1
        elif reads[i] == '^':
            i += 2  # '^' is followed by exactly one mapping-quality char
        elif reads[i] in '+-':
            match = re.findall(r'[+-](\d+)[ACGTNacgtn*]+', reads[i:])
            if match:
                digit = match[0]
                i += 1 + len(digit) + int(digit)
            else:
                i += 1
        else:
            logger.warning('mpileup parser: unknown char %r in %s[%d]', reads[i], reads, i)
            i += 1
    return counts


class MinorityReport:
    """Compute minority base distributions from samtools mpileup output."""

    def minority_base_distribution(self, mpileup_path, out_path, blacklist=None):
        """
        Parse a mpileup file and write minority base frequency files.

        Produces two output files:
          - <out_path>          : one minority frequency per line (no position)
          - <out_path>.withpos  : tab-separated position and minority frequency
        """
        if blacklist is None:
            blacklist = set()

        mpileup_path = Path(mpileup_path)
        out_path = Path(out_path)
        withpos_path = Path(str(out_path) + '.withpos')

        open_fn = gzip.open if mpileup_path.suffix == '.gz' else open

        with open_fn(mpileup_path, 'rt', encoding='utf-8') as fin, \
             open(out_path, 'w', encoding='utf-8') as fout, \
             open(withpos_path, 'w', encoding='utf-8') as fout_pos:
            for line in fin:
                data = line.strip().split('\t')
                if len(data) < 6:
                    continue
                if data[1] in blacklist:
                    continue
                cov = int(data[3])
                if 30 < cov < 100:
                    ref = data[2].upper()
                    types = parse_pile(data[4], ref)
                    minority_freq = sorted(
                        [types['A'], types['G'], types['C'], types['T']]
                    )[2] / cov
                    if minority_freq > 0:
                        fout_pos.write(f"{data[1]}\t{minority_freq}\n")
                        fout.write(f"{minority_freq}\n")

        logger.info("Wrote minority distribution to %s and %s", out_path, withpos_path)
        return out_path, withpos_path

    def run(self, mpileup_path, out_path, blacklist_path=None):
        """Run minority base distribution on a pre-computed mpileup file."""
        blacklist = set()
        if blacklist_path:
            blacklist = read_blacklist(blacklist_path)
        return self.minority_base_distribution(mpileup_path, out_path, blacklist)
