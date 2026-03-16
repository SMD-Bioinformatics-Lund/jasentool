"""Download genome FASTA and GFF files from NCBI Datasets v2 API (Issue #20)."""
# Authors: Markus Johansson & Ryan Kennedy

import os
import re
import shutil
import subprocess

from jasentool.log import get_logger
from jasentool.utils import Utils

logger = get_logger(__name__)


def _mkdir(dirpath):
    os.makedirs(dirpath, exist_ok=True)


def _remove_file(filepath):
    if os.path.exists(filepath):
        os.remove(filepath)


def _remove_directory(dirpath):
    try:
        shutil.rmtree(dirpath)
    except FileNotFoundError:
        pass


def _remove_dir_content(dirpath):
    _remove_directory(dirpath)
    _mkdir(dirpath)


def _find_files(search_term, parent_dir):
    try:
        return sorted([
            os.path.join(parent_dir, f)
            for f in os.listdir(parent_dir)
            if re.search(search_term, f) and not f.endswith("~")
        ])
    except FileNotFoundError:
        logger.warning("Directory does not exist: %s", parent_dir)
        return []


def _index_fasta(command_str, accn, download_dir):
    try:
        proc = subprocess.Popen(
            command_str.split(),
            cwd=download_dir,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        proc.communicate()
        logger.info("Indexing complete for %s: %s", accn, command_str)
    except FileNotFoundError:
        logger.error("Indexing tool not found for command: %s", command_str)


class NCBI:
    """Download genome FASTA and GFF from NCBI Datasets v2 API."""

    def __init__(self, options):
        self.accessions = list(options.accession)
        self.output_dir = options.output_dir
        self.bwa_index = options.bwa_index
        self.fai_index = options.fai_index
        self.clean = options.clean

    def run(self):
        """Entry point: optionally clean output dir, then download each accession."""
        if self.clean:
            logger.info("Cleaning output directory: %s", self.output_dir)
            _remove_dir_content(self.output_dir)
        _mkdir(self.output_dir)
        for accn in self.accessions:
            self._process_accession(accn)

    def _process_accession(self, accn):
        logger.info("Processing accession: %s", accn)
        zip_path = os.path.join(self.output_dir, f"{accn}.zip")
        url = (
            f"https://api.ncbi.nlm.nih.gov/datasets/v2/genome/accession/{accn}/download"
            f"?include_annotation_type=GENOME_FASTA&include_annotation_type=GENOME_GFF"
            f"&include_annotation_type=SEQUENCE_REPORT&hydrated=FULLY_HYDRATED&filename={accn}.zip"
        )
        if not Utils.download_and_save_file(url, zip_path, max_retries=5):
            logger.error("Skipping %s due to download failure.", accn)
            return
        if not Utils.unzip(zip_path, self.output_dir):
            logger.error("Skipping %s due to unzip failure.", accn)
            _remove_file(zip_path)
            return
        try:
            data_dir = os.path.join(self.output_dir, f"ncbi_dataset/data/{accn}")
            fasta_files = _find_files(rf'^{accn}.*\.(fna|fasta)$', data_dir)
            if not fasta_files:
                logger.warning("No FASTA file found for %s. Skipping.", accn)
                return
            fasta_source = fasta_files[0]
            gff_source = os.path.join(data_dir, "genomic.gff")
            fasta_dest = os.path.join(self.output_dir, f"{accn}.fasta")
            gff_dest = os.path.join(self.output_dir, f"{accn}.gff")
            if os.path.exists(fasta_source):
                shutil.copy(fasta_source, fasta_dest)
                logger.info("Copied FASTA: %s", fasta_dest)
            if os.path.exists(gff_source):
                shutil.copy(gff_source, gff_dest)
                logger.info("Copied GFF: %s", gff_dest)
            if self.bwa_index:
                _index_fasta(f"bwa index {fasta_dest}", accn, self.output_dir)
            if self.fai_index:
                _index_fasta(f"samtools faidx {fasta_dest}", accn, self.output_dir)
        except Exception as exc:  # pylint: disable=broad-except
            logger.error("Error while processing %s: %s", accn, exc)
        finally:
            _remove_directory(os.path.join(self.output_dir, "ncbi_dataset"))
            _remove_file(zip_path)
