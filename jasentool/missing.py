"""Module to find samples that have not been run via jasen"""

import os
import re
from jasentool.log import get_logger
from jasentool.sample_utils import (
    check_format,
    filter_by_keys,
    find_files,
)

logger = get_logger(__name__)

class Missing:
    """Class for locating expected samples that are missing from a given directory"""
    @staticmethod
    def rm_double_dmltplx(read_files):
        """Exclude files that have been demultiplexed twice"""
        first_reads = read_files[0]
        for read_file in read_files[1:]:
            errors = 0
            for idx, _ in enumerate(first_reads):
                if first_reads[idx] != read_file[idx]:
                    errors += 1
            if errors == 1:
                return [first_reads, read_file]
        return read_files

    @staticmethod
    def edit_read_paths(reads, restore_dir):
        """Edit read paths to show intended location to be coppied to"""
        filename = os.path.join(restore_dir, reads.split("BaseCalls/")[1])
        read1, read2 = [filename.rstrip(".spring") + f"_R{i}_001.fastq.gz" for i in [1, 2]]
        return os.path.join(restore_dir, reads.split("BaseCalls/")[1]), [read1, read2]

    @staticmethod
    def get_seqrun_from_filepath(filepath):
        """Extract and return the sequencing run identifier (YYMMDD format) from a filepath."""
        path_segments = filepath.split("/")
        pattern = r'^\d{6}'  # Regular expression pattern for YYMMDD format
        for path_segment in path_segments:
            match = re.search(pattern, path_segment)
            if match:
                return path_segment
        return None

    @staticmethod
    def check_file_cp(reads, restore_dir):
        """Check that file not already coppied to restore directory"""
        checked_reads = []
        restore_dirs = set([restore_dir.rstrip("/"), "/fs2/seqdata/restored"])
        for filepath in reads:
            filename = os.path.basename(filepath)
            if filepath.startswith("/fs") and os.path.exists(filepath):
                checked_reads.append(filepath)
            else:
                for directory in restore_dirs:
                    read_fpath = os.path.join(directory, filename)
                    if (
                        os.path.exists(read_fpath) and
                        not os.path.isdir(read_fpath) and
                        len(checked_reads) != 2
                    ):
                        checked_reads.append(read_fpath)
        if len(checked_reads) == 0:
            checked_reads = [
                os.path.join(restore_dir, os.path.basename(read_filepath))
                for read_filepath in reads
            ]
        return checked_reads

    @staticmethod
    def parse_sample_sheet(sample_sheet, restore_dir, id_seqrun_dict):
        """Parse sample sheets for sample meta data"""
        csv_dict = {}
        seqrun = Missing.get_seqrun_from_filepath(sample_sheet)
        with open(sample_sheet, "r", encoding="utf-8") as fin:
            for line in fin:
                if line.endswith("saureus\n"):
                    line = line.rstrip()
                    sample_id = line.split(",")[-1].split("_")[1]
                    try:
                        if seqrun != id_seqrun_dict[sample_id]:
                            continue
                    except KeyError:
                        continue
                    species = line.split(",")[-1].split("_")[2]
                    try:
                        clarity_sample_meta = line.split(",")[0].split(":")[1]
                    except IndexError:
                        clarity_sample_meta = line.split(",")[0]
                    try:
                        clarity_group_id = clarity_sample_meta.split("_")[1]
                    except IndexError:
                        clarity_group_id = clarity_sample_meta
                    clarity_sample_id = clarity_sample_meta.split("_")[0]
                    if len(clarity_sample_id) < 4:
                        clarity_sample_id = sample_id
                        clarity_group_id = sample_id
                    if ":" in line:
                        parent_dir = os.path.join(
                            line.split(":")[0].rstrip("SampleSheet.csv"),
                            "Data/Intensities/BaseCalls/"
                        )
                    else:
                        parent_dir = os.path.join(
                            os.path.dirname(sample_sheet),
                            "Data/Intensities/BaseCalls/"
                        )
                    try:
                        paired_reads = find_files(r'^' + clarity_sample_id, parent_dir)
                        if len(paired_reads) == 2 and paired_reads[0].endswith(".gz"):
                            restored_reads_fpaths = Missing.check_file_cp(paired_reads, restore_dir)
                            csv_dict[sample_id] = [
                                clarity_sample_id,
                                clarity_group_id,
                                species,
                                seqrun,
                                restored_reads_fpaths,
                                None,
                                paired_reads
                            ]
                        elif len(paired_reads) == 1 and paired_reads[0].endswith(".spring"):
                            spring_fpaths = paired_reads
                            (restored_spring_fpaths, paired_reads) = list(map(
                                Missing.edit_read_paths,
                                spring_fpaths,
                                [restore_dir]*len(spring_fpaths)
                            ))[0]
                            csv_dict[sample_id] = [
                                clarity_sample_id,
                                clarity_group_id,
                                species,
                                seqrun,
                                paired_reads,
                                spring_fpaths,
                                restored_spring_fpaths
                            ]
                        elif len(paired_reads) == 4 and paired_reads[0].endswith(".gz"):
                            paired_reads = Missing.rm_double_dmltplx(paired_reads)
                            if len(paired_reads) == 2:
                                restored_reads_fpaths = Missing.check_file_cp(paired_reads, restore_dir)
                                csv_dict[sample_id] = [
                                    clarity_sample_id,
                                    clarity_group_id,
                                    species,
                                    seqrun,
                                    restored_reads_fpaths,
                                    None,
                                    paired_reads
                                ]
                            elif len(paired_reads) == 4:
                                paired_reads_string = '\n-'.join(paired_reads)
                                logger.warning("There are 4 sets of reads related to sample %s from the %s:\n-%s", sample_id, parent_dir, paired_reads_string)

                        elif len(paired_reads) == 3:
                            paired_reads = [paired_read for paired_read in paired_reads
                                            if paired_read.endswith(".fastq.gz")]
                            restored_reads_fpaths = Missing.check_file_cp(paired_reads, restore_dir)
                            csv_dict[sample_id] = [
                                clarity_sample_id,
                                clarity_group_id,
                                species,
                                seqrun,
                                restored_reads_fpaths,
                                None,
                                paired_reads
                            ]
                        elif len(paired_reads) == 6:
                            paired_reads = [paired_read for paired_read in paired_reads
                                            if paired_read.endswith(".fastq.gz")]
                            restored_reads_fpaths = Missing.check_file_cp(paired_reads, restore_dir)
                            csv_dict[sample_id] = [
                                clarity_sample_id,
                                clarity_group_id,
                                species,
                                seqrun,
                                restored_reads_fpaths,
                                None,
                                paired_reads
                            ]
                    except FileNotFoundError:
                        logger.warning("%s does not exist regarding %s. (sample sheet: %s)", parent_dir, sample_id, sample_sheet)

        return csv_dict

    @staticmethod
    def find_missing(meta_dict, analysis_dir_fnames, restore_dir):
        """Find missing samples from jasen results directory"""
        sample_runs = []
        missing_samples = []
        csv_dict = {}
        sorted_meta_dict = sorted(meta_dict, key=lambda x: x["run"], reverse=False)
        id_seqrun_dict = {sample["id"]: sample["run"].split("/")[-1] for sample in sorted_meta_dict}
        for sample in sorted_meta_dict:
            if sample["id"] not in analysis_dir_fnames:
                missing_samples.append(sample["id"])
                if sample["run"] not in sample_runs:
                    ss_dict = {}
                    sample_run_dir = check_format(sample["run"])
                    sample_sheets = find_files(r'.csv$', sample_run_dir)
                    if sample_sheets:
                        for sample_sheet in sample_sheets:
                            ss_dict |= Missing.parse_sample_sheet(sample_sheet, restore_dir, id_seqrun_dict)
                        csv_dict |= ss_dict
                    else:
                        logger.warning("No sample sheets exist in the following path: %s!", sample['run'])
                    sample_runs.append(sample["run"])

        logger.info("%d samples found", len(csv_dict.keys()))
        logger.info("%d samples missing", len(missing_samples))
        logger.info("%d duplicate sample ids", len(missing_samples) - len(set(missing_samples)))
        filtered_csv_dict, not_found = filter_by_keys(csv_dict, missing_samples)
        return filtered_csv_dict, "\n".join(not_found)

    @staticmethod
    def create_bash_script(csv_dict, restore_dir):
        """Create shell script that executes copying of files and starts nextflow analysis"""
        spring_command = ""
        shell_script_path = 'SCRIPTPATH="$( cd -- "$(dirname "$0")" >/dev/null 2>&1 ; pwd -P )"\n'
        shell_fail_count = "FAIL=0\n"
        shell_for_loop = 'for job in $PIDS; do wait $job || let "FAIL+=1"; done \nif [ "$FAIL" != "0" ]; \nthen \n\techo Failed to restore from backup \n\texit 2 \nfi \n'
        for sample in csv_dict:
            jcp_command = ""
            unspring_command = ""
            try:
                spring_fpaths, restored_fpaths = csv_dict[sample][5][0], csv_dict[sample][6]
                read1, _ = csv_dict[sample][4]
                if not os.path.exists(restored_fpaths) and not os.path.exists(read1):
                    jcp_command = f'/fs2/sw/bnf-scripts/jcp {spring_fpaths} {restore_dir}/ && '
                    unspring_command = f'/fs2/sw/bnf-scripts/unspring_file.pl {restored_fpaths} {restore_dir}/ WAIT &\nPIDS="$PIDS $!"\n'
                spring_command = spring_command + jcp_command + unspring_command
            except TypeError:
                for read_fpath in csv_dict[sample][6]:
                    jcp_command = f'/fs2/sw/bnf-scripts/jcp {read_fpath} {restore_dir}/ WAIT &\nPIDS="$PIDS $!"\n'
                    spring_command = spring_command + jcp_command
        bash_script = shell_script_path + shell_fail_count + spring_command + shell_for_loop
        return bash_script

    @staticmethod
    def remove_empty_files(csv_dict):
        """Remove fastq filepaths if the file size is < 10 mb"""
        empty_files_dict = {}
        for sample in csv_dict:
            try:
                file_size_r1 = os.path.getsize(csv_dict[sample][4][0]) / (1024 * 1024)
                file_size_r2 = os.path.getsize(csv_dict[sample][4][1]) / (1024 * 1024)
                if file_size_r1 < 10 or file_size_r2 < 10:
                    empty_files_dict[sample] = csv_dict[sample]
            except FileNotFoundError:
                logger.warning("%s read files (%s and/or %s) could not be found!", sample, csv_dict[sample][4][0], csv_dict[sample][4][1])
            except IndexError:
                logger.error("Unexpected csv_dict entry for %s: %s", sample, csv_dict[sample])
        for empty_file in list(empty_files_dict.keys()):
            csv_dict.pop(empty_file, None)
        return empty_files_dict, csv_dict
