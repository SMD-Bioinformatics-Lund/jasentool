"""Module for executing each module/class"""

import os
import sys
import json
import pprint
from bson import ObjectId

from jasentool.database import Database
from jasentool.validate import Validate
from jasentool.utils import Utils
from jasentool.missing import Missing
from jasentool.convert import Convert
from jasentool.fix import Fix
from jasentool.converge import Converge
from jasentool.qc import QC
from jasentool.count_reads import CountReads
from jasentool.ncbi import NCBI
from jasentool.bigsdb import BIGSdb
from jasentool.concatenate import Concatenate
from jasentool.create_yaml import CreateYaml
from jasentool.annotate_delly import AnnotateDelly
from jasentool.log import get_logger

logger = get_logger(__name__)

class OptionsParser:
    """Class that parses through cli arguments and executes respective modules"""
    def __init__(self, version):
        """Initiate OptionsParser class"""
        self.version = version
        self._check_python()

    def _check_python(self):
        if sys.version_info.major < 3:
            logger.error('Python 2 is no longer supported.')
            sys.exit(1)

    def _traverse_input_dir(self, input_dir):
        return [os.path.join(input_dir, filename) for filename in os.listdir(input_dir) if filename.endswith("result.json")]

    def _input_to_process(self, input_file, input_dir):
        if input_dir:
            valid_inputs = self._traverse_input_dir(input_dir)
        elif input_file:
            valid_inputs = input_file
        else:
            logger.error('No input was provided.')
            sys.exit(1)
        return valid_inputs

    def _get_output_fpaths(self, input_files, output_dir, output_file, prefix, combined_output):
        output_fpaths = []
        if output_dir:
            output_dir = os.path.expanduser(output_dir)
            if combined_output:
                output_fpaths = [os.path.join(output_dir, prefix + "combined_outputs")]
            else:
                output_fpaths = [os.path.join(output_dir, prefix + os.path.basename(os.path.splitext(input_fpath)[0])) for input_fpath in input_files]
        elif output_file:
            if len(input_files) > 1:
                logger.error('You have input %d input_files and provided an outfile instead of an out directory. Use --output-dir instead.', len(input_files))
                sys.exit(1)
            output_fpaths = [os.path.splitext(output_file)[0]]
        return output_fpaths

    def find(self, options):
        """Find entry in mongodb"""
        Database.initialize(options.db_name)
        output_fpaths = self._get_output_fpaths(options.query, options.output_dir,
                                                options.output_file, options.prefix,
                                                options.combined_output)
        for query_idx, query in enumerate(options.query):
            find = list(Database.find(options.db_collection, {"id": query}, {}))
            if not find:
                find = list(Database.find(options.db_collection, {"sample_id": query}, {}))
            find = [{key: str(value) if isinstance(value, ObjectId) else value for key, value in entry.items()} for entry in find]
            sample_pp = pprint.PrettyPrinter(indent=4)
            sample_pp.pprint(find)
            with open(output_fpaths[query_idx], 'w+', encoding="utf-8") as fout:
                json.dump(find, fout)

    def validate_pipelines(self, options):
        """Execute validation of old vs new pipeline results"""
        Database.initialize(options.db_name)
        input_files = self._input_to_process(options.input_file, options.input_dir)
        output_fpaths = self._get_output_fpaths(input_files, options.output_dir,
                                                options.output_file, options.prefix,
                                                options.combined_output)
        validate = Validate(options.input_dir, options.db_collection)
        validate.run(input_files, output_fpaths, options.combined_output, options.generate_matrix)

    def identify_missing(self, options):
        """Execute search for missing samples from new pipeline results"""
        utils = Utils()
        handler = Missing()
        db = Database()
        db.initialize(options.db_name)
        if options.sample_sheet:
            meta_dict = db.find(options.db_collection, {"metadata.QC": "OK"}, db.get_meta_fields())
            sorted_meta_dict = sorted(meta_dict, key=lambda x: x["run"], reverse=False)
            id_seqrun_dict = {sample["id"]: sample["run"].split("/")[-1] for sample in sorted_meta_dict}
            csv_dict = handler.parse_sample_sheet(options.input_file[0], options.restore_dir, id_seqrun_dict)
            utils.write_out_csv(csv_dict, options.assay, options.platform, options.output_file, options.alter_sample_id)
        if options.analysis_dir:
            log_fpath = os.path.splitext(options.missing_log)[0] + ".log"
            empty_fpath = os.path.splitext(options.output_file)[0] + "_empty.csv"
            meta_dict = db.find(options.db_collection, {"metadata.QC": "OK"}, db.get_meta_fields())
            analysis_dir_fnames = handler.parse_dir(options.analysis_dir, options.alter_sample_id)
            csv_dict, missing_samples_txt = handler.find_missing(meta_dict, analysis_dir_fnames, options.restore_dir)
            empty_files_dict, csv_dict = handler.remove_empty_files(csv_dict)
            utils.write_out_csv(csv_dict, options.assay, options.platform, options.output_file, options.alter_sample_id)
            utils.write_out_csv(empty_files_dict, options.assay, options.platform, empty_fpath, options.alter_sample_id)
            utils.write_out_txt(missing_samples_txt, log_fpath)
        if options.restore_file:
            bash_fpath = os.path.splitext(options.restore_file)[0] + ".sh"
            bash_script = handler.create_bash_script(csv_dict, options.restore_dir)
            utils.write_out_txt(bash_script, bash_fpath)

    def transform_file_format(self, options):
        """Execute conversion of file formats"""
        utils = Utils()
        handler = Convert()
        input_file = options.input_file[0]
        output_fpath = os.path.splitext(options.output_file)[0] + "." + options.out_format
        in_format = os.path.splitext(input_file)[1].lstrip(".")
        if in_format in ("tsv", "csv") and options.out_format == "bed":
            output_txt = handler.targets2bed(input_file, options.accession)
            utils.write_out_txt(output_txt, output_fpath)

    def reformat_csv(self, options):
        """Execute fixing of file to desired format(s)"""
        utils = Utils()
        handler = Fix()
        csv_files, assays = handler.fix_csv(options.csv_file, options.output_file, options.alter_sample_id)
        batch_files = handler.fix_sh(options.sh_file, options.output_file, assays) if options.sh_file else options.sh_file
        if (options.remote or options.auto_start) and batch_files:
            utils.copy_batch_and_csv_files(batch_files, csv_files, options.remote_dir, options.remote_hostname, options.auto_start or options.remote)
            if options.auto_start:
                utils.start_remote_pipelines(batch_files, options.remote_hostname, options.remote_dir)

    def converge_catalogues(self, options):
        """Execute convergence of mutation catalogues"""
        handler = Converge(options.output_dir)
        handler.run(options.save_dbs)

    def post_align_qc(self, options):
        """Execute retrieval of qc results"""
        qc = QC(options)
        json_result = qc.run()
        qc.write_json_result(json_result, options.output_file)

    def count_reads(self, options):
        """Count reads in FASTQ file(s) and write JSON result."""
        handler = CountReads()
        result = handler.run(options.input_file, getattr(options, 'sample_id', None))
        with open(options.output_file, 'w', encoding="utf-8") as fout:
            json.dump(result, fout, indent=2)

    def download_ncbi(self, options):
        """Download genome FASTA and GFF from NCBI Datasets v2 API."""
        NCBI(options).run()

    def download_bigsdb(self, options):
        """Download cgMLST scheme alleles from PubMLST or BIGSdb Pasteur via OAuth1."""
        BIGSdb(options).run()

    def concatenate_files(self, options):
        """Concatenate multiple YAML files into one"""
        Concatenate.run(options.input_files, options.output_file)

    def create_yaml(self, options):
        """Create YAML input file for Bonsai upload"""
        CreateYaml().run(options)

    def annotate_delly(self, options):
        """Annotate Delly SV VCF with gene/locus_tag from a tabix BED."""
        AnnotateDelly().run(options.vcf, options.bed, options.output)

    def parse_options(self, options):
        """Options parser"""
        if options.subparser_name == 'find':
            self.find(options)

        elif options.subparser_name == 'validate-pipelines':
            self.validate_pipelines(options)

        elif options.subparser_name == 'identify-missing':
            self.identify_missing(options)

        elif options.subparser_name == 'transform-file-format':
            self.transform_file_format(options)

        elif options.subparser_name == 'reformat-csv':
            self.reformat_csv(options)

        elif options.subparser_name == 'converge-catalogues':
            self.converge_catalogues(options)

        elif options.subparser_name == 'post-align-qc':
            self.post_align_qc(options)

        elif options.subparser_name == 'count-reads':
            self.count_reads(options)
