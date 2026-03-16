"""Build a Kraken2 database from NCBI RefSeq (human/bacterial/viral) (Issue #18)."""

import io
import os
import re
import subprocess
import tempfile

import requests
import pandas as pd
from Bio import SeqIO

from jasentool.log import get_logger

logger = get_logger(__name__)

_ASSEMBLY_URLS = {
    "refseq": "https://ftp.ncbi.nlm.nih.gov/genomes/refseq/assembly_summary_refseq.txt",
    "bacteria": "https://ftp.ncbi.nlm.nih.gov/genomes/refseq/bacteria/assembly_summary.txt",
    "viral": "https://ftp.ncbi.nlm.nih.gov/genomes/refseq/viral/assembly_summary.txt",
}


def _ftp_to_https(url):
    """Convert an ftp:// URL to https://."""
    return re.sub(r'^ftp://', 'https://', url)


def _fetch_assembly_summary(url):
    """Download an NCBI assembly summary file and return a pandas DataFrame."""
    logger.info("Fetching assembly summary: %s", url)
    resp = requests.get(url, timeout=120)
    resp.raise_for_status()
    lines = resp.text.splitlines()
    # Line 0: comment describing columns; line 1: actual header (starts with '# ')
    # Strip leading '# ' from the header line so pandas sees column names.
    if lines and lines[0].startswith("# See"):
        lines.pop(0)
    if lines and lines[0].startswith("# "):
        lines[0] = lines[0][2:]
    return pd.read_table(io.StringIO("\n".join(lines)), dtype="unicode")


def _download_genome_fna(ftp_path, output_dir, asm_name):
    """Download a single .fna.gz genome file and decompress it in output_dir."""
    import gzip
    https_path = _ftp_to_https(ftp_path)
    # Construct the FNA filename following NCBI naming convention
    accession = os.path.basename(ftp_path)
    fna_filename = f"{accession}_{asm_name}_genomic.fna.gz"
    url = f"{https_path}/{fna_filename}"
    gz_dest = os.path.join(output_dir, fna_filename)
    fna_dest = gz_dest[:-3]  # strip .gz
    if os.path.exists(fna_dest):
        logger.info("Already exists, skipping: %s", fna_dest)
        return fna_dest
    logger.info("Downloading: %s", url)
    try:
        resp = requests.get(url, stream=True, timeout=120)
        resp.raise_for_status()
        with open(gz_dest, "wb") as fh:
            for chunk in resp.iter_content(chunk_size=8192):
                fh.write(chunk)
        with gzip.open(gz_dest, "rb") as gz_fh, open(fna_dest, "wb") as out_fh:
            out_fh.write(gz_fh.read())
        os.remove(gz_dest)
        return fna_dest
    except requests.exceptions.RequestException as exc:
        logger.warning("Failed to download %s: %s", url, exc)
        return None


def _fasta_to_kraken_format(fna_path, output_handle):
    """Re-write FASTA records with kraken:taxid header from GenBank source feature."""
    records = SeqIO.parse(fna_path, "fasta")
    for record in records:
        # Kraken expects >seqid|kraken:taxid|<taxid> format when pre-tagged,
        # but standard FNA files from NCBI already work with kraken2-build --add-to-library.
        output_handle.write(f">{record.id}\n{str(record.seq)}\n")


class Krakendb:
    """Build a Kraken2 database from NCBI RefSeq human, bacterial, and viral genomes."""

    def __init__(self, options):
        self.output_dir = options.output_dir
        self.db_name = options.db_name
        self.threads = options.threads

    @property
    def _db_path(self):
        return os.path.join(self.output_dir, self.db_name)

    def run(self):
        """Download genomes, build taxonomy, add to library, and build the Kraken2 DB."""
        os.makedirs(self.output_dir, exist_ok=True)
        genome_dir = os.path.join(self.output_dir, "genomes")
        os.makedirs(genome_dir, exist_ok=True)

        fna_files = []
        fna_files += self._download_human_genome(genome_dir)
        fna_files += self._download_bacterial_genomes(genome_dir)
        fna_files += self._download_viral_genomes(genome_dir)

        self._build_taxonomy()
        for fna_path in fna_files:
            if fna_path and os.path.exists(fna_path):
                self._add_to_library(fna_path)
        self._build_db()

    # ------------------------------------------------------------------
    # Download helpers
    # ------------------------------------------------------------------

    def _download_human_genome(self, genome_dir):
        logger.info("Fetching human reference genome (taxid 9606)...")
        summary = _fetch_assembly_summary(_ASSEMBLY_URLS["refseq"])
        filtered = summary[
            (summary["taxid"] == "9606") &
            (
                (summary["refseq_category"] == "reference genome") |
                (summary["refseq_category"] == "representative genome")
            )
        ]
        return self._download_rows(filtered, genome_dir)

    def _download_bacterial_genomes(self, genome_dir):
        logger.info("Fetching bacterial complete genomes...")
        summary = _fetch_assembly_summary(_ASSEMBLY_URLS["bacteria"])
        filtered = summary[
            (summary["version_status"] == "latest") &
            (summary["assembly_level"] == "Complete Genome")
        ]
        return self._download_rows(filtered, genome_dir)

    def _download_viral_genomes(self, genome_dir):
        logger.info("Fetching viral complete genomes...")
        summary = _fetch_assembly_summary(_ASSEMBLY_URLS["viral"])
        filtered = summary[
            (summary["version_status"] == "latest") &
            (summary["assembly_level"] == "Complete Genome")
        ]
        return self._download_rows(filtered, genome_dir)

    @staticmethod
    def _download_rows(dataframe, genome_dir):
        fna_files = []
        for _, row in dataframe.iterrows():
            ftp_path = row.get("ftp_path", "")
            asm_name = row.get("asm_name", "")
            if not ftp_path or ftp_path == "na":
                continue
            fna_path = _download_genome_fna(ftp_path, genome_dir, asm_name)
            if fna_path:
                fna_files.append(fna_path)
        return fna_files

    # ------------------------------------------------------------------
    # Kraken2-build helpers
    # ------------------------------------------------------------------

    def _run_kraken2_build(self, args):
        cmd = ["kraken2-build"] + args + ["--db", self._db_path, "--threads", str(self.threads)]
        logger.info("Running: %s", " ".join(cmd))
        result = subprocess.run(cmd, check=False)
        if result.returncode != 0:
            logger.warning("kraken2-build exited with code %d", result.returncode)

    def _build_taxonomy(self):
        logger.info("Downloading taxonomy...")
        self._run_kraken2_build(["--download-taxonomy", "--use-ftp"])

    def _add_to_library(self, fna_path):
        self._run_kraken2_build(["--add-to-library", fna_path])

    def _build_db(self):
        logger.info("Building Kraken2 database: %s", self._db_path)
        self._run_kraken2_build(["--build"])
