"""Command line interface module"""

import argparse
from contextlib import contextmanager

@contextmanager
def subparser(parser, name, desc):
    """Yield subparser"""
    yield parser.add_parser(name, conflict_handler='resolve', help=desc,
                            formatter_class=argparse.RawDescriptionHelpFormatter)

@contextmanager
def mutex_group(parser, required):
    """Yield mutually exclusive group"""
    arg_type = "required" if required else "optional"
    group = parser.add_argument_group(f'mutually exclusive {arg_type} arguments')
    yield group.add_mutually_exclusive_group(required=required)

@contextmanager
def arg_group(parser, name):
    """Yield mutually argument group"""
    yield parser.add_argument_group(name)

def __query(group, required):
    """Add query argument to group"""
    group.add_argument('-q', '--query', required=required, nargs='+', help='sample query')

def __sample_id(group, required):
    """Add sample_id argument to group"""
    group.add_argument('--sample_id', required=required, type=str, help='sample ID')

def __input_dir(group, required, help):
    """Add input_dir argument to group"""
    group.add_argument('--input_dir', required=required, help=help)

def __input_file(group, required, help):
    """Add input_file argument to group"""
    group.add_argument('-i', '--input_file', required=required, nargs='+', help=help)

def __csv_file(group, required, help):
    """Add csv_file argument to group"""
    group.add_argument('--csv_file', required=required, help=help)

def __sh_file(group, required, help):
    """Add sh_file argument to group"""
    group.add_argument('--sh_file', required=required, default=None, help=help)

def __bam_file(group, required):
    """Add bam_file argument to group"""
    group.add_argument('--bam_file', required=required, type=str, help='input bam file')

def __bed_file(group, required):
    """Add bed_file argument to group"""
    group.add_argument('--bed_file', required=required, type=str, help='input bed file')

def __baits_file(group, required):
    """Add baits_file argument to group"""
    group.add_argument('--baits_file', required=required, type=str, default=None,
                       help='input baits file')

def __reference(group, required, help):
    """Add reference argument to group"""
    group.add_argument('--reference', required=required, type=str, help=help)

def __output_file(group, required, help):
    """Add output_file argument to group"""
    group.add_argument('-o', '--output_file', required=required, type=str, help=help)

def __output_dir(group, required):
    """Add output_dir argument to group"""
    group.add_argument('--output_dir', required=required, type=str,
                       help='directory to output files')

def __analysis_dir(group, required):
    """Add analysis_dir argument to group"""
    group.add_argument('--analysis_dir', required=required, type=str,
                       help='analysis results dir containing jasen results')

def __restore_dir(group, required):
    """Add restore_dir argument to group"""
    group.add_argument('--restore_dir', required=required, type=str,
                       default='/fs2/seqdata/restored',
                       help='directory user wishes spring files to be restored to')

def __remote_dir(group, required):
    """Add remote_dir argument to group"""
    group.add_argument('--remote_dir', required=required, type=str,
                       default='/fs1/bjorn/jasen',
                       help='directory user wishes spring files to be restored to')

def __restore_file(group, required):
    """Add restore_file argument to group"""
    group.add_argument('--restore_file', required=required, type=str,
                       help='filepath bash shell script (.sh) to be output')

def __missing_log(group, required):
    """Add missing_log argument to group"""
    group.add_argument('--missing_log', required=required, type=str,
                       default='missing_samples.log',
                       help='file containing missing files')

def __assay(group, required):
    """Add assay argument to group"""
    group.add_argument('--assay', required=required, type=str,
                       default='jasen-saureus-dev',
                       help='assay for jasen to run')

def __platform(group, required):
    """Add platform argument to group"""
    group.add_argument('--platform', required=required, type=str,
                       default='illumina',
                       help='sequencing platform for jasen to run')

def __uri(group):
    """Add mongodb address argument to group"""
    group.add_argument('--address', '--uri',
                       default='mongodb://localhost:27017/',
                       help='Mongodb host address. \
                        Use: `sudo lsof -iTCP -sTCP:LISTEN | grep mongo` to get address')

def __db_name(group, required):
    """Add db_name argument to group"""
    group.add_argument('--db_name', required=required,
                       help='Mongodb database name address. \
                        Use: `show dbs` to get db name')

def __db_collection(group, required):
    """Add db_collection argument to group"""
    group.add_argument('--db_collection', required=required,
                       help='Mongodb collection name. \
                        Use: `show collections` to get db collection')

def __out_format(group, required):
    """Add out_format argument to group"""
    group.add_argument('-f', '--out_format', required=required, type=str,
                       default="bed", help='output format')

def __accession(group, required):
    """Add accession argument to group"""
    group.add_argument('-a', '--accession', required=required, type=str, help='accession number')

def __remote_hostname(group, required):
    """Add remote_hostname argument to group"""
    group.add_argument('--remote_hostname', required=required, type=str,
                       default='rs-fe1.lunarc.lu.se', help='remote hostname')

def __prefix(group):
    """Add prefix argument to group"""
    group.add_argument('--prefix', type=str, default='jasentool_results_',
                       help='prefix for all output files')

def __auto_start(group, required):
    """Add auto_start argument to group"""
    group.add_argument('--auto_start', required=required, dest='auto_start', action='store_true',
                       default=False, help='automatically start')

def __remote(group, required):
    """Add remote argument to group"""
    group.add_argument('--remote', required=required, dest='remote', action='store_true',
                       default=False, help='remote copy')

def __combined_output(group):
    """Add combined_output argument to group"""
    group.add_argument('--combined_output', dest='combined_output', action='store_true',
                       help='combine all of the outputs into one output')

def __generate_matrix(group):
    """Add generate_matrix argument to group"""
    group.add_argument('--generate_matrix', dest='generate_matrix', action='store_true',
                       help='generate cgmlst matrix')

def __save_dbs(group):
    """Save all intermediary dbs created for TBProfiler db convergence"""
    group.add_argument('--save_dbs', dest='save_dbs', action='store_true',
                       help='save all intermediary dbs created for TBProfiler db convergence')

def __sample_sheet(group, required):
    """Add sample_sheet argument to group"""
    group.add_argument('--sample_sheet', required=required, dest='sample_sheet',
                       action='store_true', help='sample sheet input')

def __alter_sample_id(group, required):
    """Add sample_sheet argument to group"""
    group.add_argument('--alter_sample_id', required=required,
                       dest='alter_sample_id', action='store_true', default=False,
                       help='alter sample id to be lims ID + sequencing run')

def __cpus(group):
    """Add cpus argument to group"""
    group.add_argument('--cpus', dest='cpus', type=int, default=2, help='input cpus')

def __help(group):
    """Add help argument to group"""
    group.add_argument('-h', '--help', action='help', help='show help message')

def get_main_parser():
    """Get/build the main argument parser"""
    main_parser = argparse.ArgumentParser(prog='jasentool', conflict_handler='resolve')
    sub_parsers = main_parser.add_subparsers(help='--', dest='subparser_name')
    with subparser(sub_parsers, 'find', 'Find sample from given mongo db') as parser:
        with mutex_group(parser, required=True) as group:
            __output_dir(group, required=False)
            __output_file(group, required=False, help='path to mongo db output file')
        with arg_group(parser, 'required named arguments') as group:
            __query(group, required=True)
            __db_name(group, required=True)
            __db_collection(group, required=True)
        with arg_group(parser, 'optional arguments') as group:
            __combined_output(group)
            __uri(group)
            __prefix(group)
            __help(group)

    with subparser(sub_parsers, 'insert', 'Insert sample(s) into db') as parser:
        with mutex_group(parser, required=True) as group:
            __input_file(group, required=False, help='path to json file to be inserted into db')
            __input_dir(group, required=False, help='path to directory containing sample files')
        with arg_group(parser, 'required named arguments') as group:
            __db_name(group, required=True)
            __db_collection(group, required=True)
        with arg_group(parser, 'optional arguments') as group:
            __combined_output(group)
            __uri(group)
            __help(group)

    with subparser(sub_parsers, 'validate', 'Compare results from new pipeline to old results') as parser:
        with mutex_group(parser, required=True) as group:
            __input_file(group, required=False, help='input filepath(s)')
            __input_dir(group, required=False, help='path to directory containing sample files')
        with mutex_group(parser, required=True) as group:
            __output_dir(group, required=False)
            __output_file(group, required=False, help='path to mongo db output file')
        with arg_group(parser, 'required named arguments') as group:
            __db_name(group, required=True)
            __db_collection(group, required=True)
        with arg_group(parser, 'optional arguments') as group:
            __combined_output(group)
            __generate_matrix(group)
            __uri(group)
            __prefix(group)
            __help(group)

    with subparser(sub_parsers, 'missing', 'Find missing sample data from old runs') as parser:
        with arg_group(parser, 'required named arguments') as group:
            __output_file(group, required=True, help='path to mongo db output file')
            __db_name(group, required=True)
            __db_collection(group, required=True)
        with arg_group(parser, 'optional arguments') as group:
            __analysis_dir(group, required=False)
            __restore_dir(group, required=False)
            __restore_file(group, required=False)
            __missing_log(group, required=False)
            __assay(group, required=False)
            __platform(group, required=False)
            __sample_sheet(group, required=False)
            __alter_sample_id(group, required=False)
            __help(group)

    with subparser(sub_parsers, 'convert', 'Convert file format') as parser:
        with arg_group(parser, 'required named arguments') as group:
            __input_file(group, required=True, help='path to targets tsv file')
            __output_file(group, required=True, help='path to mongo db output file')
        with arg_group(parser, 'optional arguments') as group:
            __out_format(group, required=False)
            __accession(group, required=False)
            __help(group)

    with subparser(sub_parsers, 'fix', 'Fix bjorn microbiology csv file') as parser:
        with arg_group(parser, 'required named arguments') as group:
            __csv_file(group, required=True, help='path to bjorn csv file')
            __output_file(group, required=True, help='path to fixed output csv file')
        with arg_group(parser, 'optional arguments') as group:
            __sh_file(group, required=False, help='path to bjorn sh file')
            __remote_dir(group, required=False)
            __remote_hostname(group, required=False)
            __remote(group, required=False)
            __auto_start(group, required=False)
            __alter_sample_id(group, required=False)
            __help(group)

    with subparser(sub_parsers, 'converge', 'Converge TB mutation catalogues') as parser:
        with arg_group(parser, 'optional arguments') as group:
            __output_dir(group, required=False)
            __save_dbs(group)
            __help(group)

    with subparser(sub_parsers, 'qc', 'Run qc on bwa alignment') as parser:
        with arg_group(parser, 'required named arguments') as group:
            __sample_id(group, required=True)
            __bam_file(group, required=True)
            __reference(group, required=True, help='reference fasta file')
            __output_file(group, required=True, help='path to qc json output file')
        with arg_group(parser, 'optional arguments') as group:
            __bed_file(group, required=False)
            __baits_file(group, required=False)
            __cpus(group)
            __help(group)

    return main_parser
