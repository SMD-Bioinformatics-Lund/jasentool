"""Module for utility tools"""

import os
import csv
import shutil
import pathlib
import subprocess
from time import sleep
from zipfile import ZipFile, BadZipFile
import requests
from jasentool.log import get_logger

logger = get_logger(__name__)

class Utils:
    """Class containing utilities used throughout jasentool"""
    @staticmethod
    def write_out_csv(csv_dict, assay, platform, out_fpath, alter_sample_id=False):
        """Write out file as csv"""
        with open(out_fpath, 'w+', encoding="utf-8") as csvfile:
            fieldnames = ["id", "clarity_sample_id", "sample_name", "group", "species", "assay",
                          "platform", "sequencing_run", "read1", "read2"] #header
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for sample in csv_dict:
                lims_id = csv_dict[sample][0]
                sequencing_run = csv_dict[sample][3]
                sample_id = str(lims_id.lower() + "_" + sequencing_run.lower()) if alter_sample_id else sample
                row_dict = {"id": sample_id,
                            "clarity_sample_id": lims_id,
                            "sample_name": sample,
                            "group": csv_dict[sample][1], "species": csv_dict[sample][2],
                            "assay": assay, "platform": platform,
                            "sequencing_run": sequencing_run,
                            "read1": csv_dict[sample][4][0],
                            "read2": csv_dict[sample][4][1]} #write rows to CSV
                writer.writerow(row_dict)

    @staticmethod
    def write_out_txt(output_txt, out_fpath):
        """Write out file as text"""
        with open(out_fpath, 'w+', encoding="utf-8") as fout:
            fout.write(output_txt)

    @staticmethod
    def pipeline_ready(batch_file):
        """Check if pipeline exists"""
        assays = ['saureus', 'ecoli', 'mtuberculosis']
        for assay in assays:
            if assay in batch_file:
                return True
        return False

    @staticmethod
    def copy_batch_and_csv_files(batch_files, csv_files, remote_dir, remote_hostname, remote=False):
        """Copy shell and csv files to desired (remote) location"""
        if remote:
            # Copy files to remote server using ssh/scp
            _ = subprocess.run(
                f'ssh {remote_hostname} mkdir -p {remote_dir}',
                shell=True
            )
            _ = subprocess.run(
                f'scp {" ".join(batch_files)} {" ".join(csv_files)} {remote_hostname}:{remote_dir}',
                shell=True,
                stdout=subprocess.PIPE,
                universal_newlines=True
            )
        else:
            # Copy files to a local directory
            pathlib.Path(remote_dir).mkdir(parents=True, exist_ok=True)
            for fin in batch_files + csv_files:
                shutil.copy(fin, remote_dir)

    @staticmethod
    def start_remote_pipelines(batch_files, remote_hostname, remote_dir):
        """Start nextflow pipelines on a remote server"""
        for batch_file in batch_files:
            if Utils.pipeline_ready(batch_file):
                sleep(10.0) # Avoid maxing SSH auth connections
                _ = subprocess.Popen(
                    ["ssh", remote_hostname,
                     "bash", f"{remote_dir}/{os.path.basename(batch_file)}"],
                    close_fds=True
                )

    @staticmethod
    def download_and_save_file(url, output_filepath, timeout=600, max_retries=1):
        """Download the file and save it to the user-specified path with a timeout."""
        for attempt in range(max_retries):
            try:
                response = requests.get(url, stream=True, timeout=timeout)
                if response.status_code == 429:
                    wait_time = (2 ** attempt) + 1
                    logger.warning("Rate limited (429). Retrying in %d seconds...", wait_time)
                    sleep(wait_time)
                    continue
                response.raise_for_status()
                with open(output_filepath, 'wb') as output_file:
                    for chunk in response.iter_content(chunk_size=8192):
                        output_file.write(chunk)
                logger.info("File downloaded and saved to: %s", output_filepath)
                return True
            except requests.exceptions.RequestException as error_code:
                wait_time = (2 ** attempt) + 1
                logger.warning("Attempt %d failed: %s", attempt + 1, error_code)
                if attempt < max_retries - 1:
                    logger.info("Retrying in %d seconds...", wait_time)
                    sleep(wait_time)
                else:
                    logger.error("Max retries reached. Giving up.")
        return False

    @staticmethod
    def unzip(zip_file, outdir):
        """Unzip zip file. Returns True on success, False if the archive is invalid."""
        try:
            with ZipFile(zip_file, 'r') as zip_object:
                zip_object.extractall(path=outdir)
        except BadZipFile:
            logger.error("Invalid or corrupt zip file: %s", zip_file)
            return False
        return True

    @staticmethod
    def copy_file(source, destination):
        """Copy file from source to destination"""
        try:
            shutil.copy(source, destination)
            logger.debug("File copied from %s to %s", source, destination)
        except Exception as error_code:
            logger.error("Error copying file: %s", error_code)

    @staticmethod
    def get_aa_dict():
        """Amino acid one letter translations"""
        return {
            'Ala': 'A',
            'Arg': 'R',
            'Asn': 'N',
            'Asp': 'D',
            'Asx': 'B',
            'Cys': 'C',
            'Glu': 'E',
            'Gln': 'Q',
            'Glx': 'Z',
            'Gly': 'G',
            'His': 'H',
            'Ile': 'I',
            'Leu': 'L',
            'Lys': 'K',
            'Met': 'M',
            'Phe': 'F',
            'Pro': 'P',
            'Ser': 'S',
            'Thr': 'T',
            'Trp': 'W',
            'Tyr': 'Y',
            'Val': 'V',
            "Stop":"*",
            "-":"-"
        }
