"""Command line interface module"""
# pylint: disable=too-many-arguments,too-many-positional-arguments

import types
import logging

import click

from jasentool import __version__
from jasentool.log import setup_logging
from jasentool.main import OptionsParser


def _parser():
    return OptionsParser(__version__)


@click.group()
@click.version_option(__version__)
@click.option('-v', '--verbose', is_flag=True, default=False, help='Enable debug logging')
def cli(verbose):
    """Multipurpose tool for the JASEN pipeline and Bonsai."""
    setup_logging(level=logging.DEBUG if verbose else logging.INFO)


@cli.command('find')
@click.option('-q', '--query', required=True, multiple=True, help='Sample query')
@click.option('--db-name', required=True, help='MongoDB database name')
@click.option('--db-collection', required=True, help='MongoDB collection name')
@click.option('-o', '--output-file', default=None, help='Path to output file')
@click.option('--output-dir', default=None, help='Path to output directory')
@click.option('--combined-output', is_flag=True, default=False,
              help='Combine all outputs into one output')
@click.option('--address', '--uri', default='mongodb://localhost:27017/',
              help='MongoDB address')
@click.option('--prefix', default='jasentool_results_', help='Output file prefix')
def find_cmd(query, db_name, db_collection, output_file, output_dir,
             combined_output, address, prefix):
    """Find sample from given MongoDB."""
    if not output_file and not output_dir:
        raise click.UsageError("One of --output-file or --output-dir is required.")
    if output_file and output_dir:
        raise click.UsageError("--output-file and --output-dir are mutually exclusive.")
    options = types.SimpleNamespace(
        query=list(query), db_name=db_name, db_collection=db_collection,
        output_file=output_file, output_dir=output_dir,
        combined_output=combined_output, address=address, prefix=prefix,
    )
    _parser().find(options)


@cli.command('validate-pipelines')
@click.option('-i', '--input-file', multiple=True, default=None,
              help='Input filepath(s)')
@click.option('--input-dir', default=None,
              help='Path to directory containing sample files')
@click.option('-o', '--output-file', default=None, help='Path to output file')
@click.option('--output-dir', default=None, help='Path to output directory')
@click.option('--db-name', required=True, help='MongoDB database name')
@click.option('--db-collection', required=True, help='MongoDB collection name')
@click.option('--combined-output', is_flag=True, default=False,
              help='Combine all outputs into one output')
@click.option('--generate-matrix', is_flag=True, default=False,
              help='Generate cgMLST matrix')
@click.option('--address', '--uri', default='mongodb://localhost:27017/',
              help='MongoDB address')
@click.option('--prefix', default='jasentool_results_', help='Output file prefix')
def validate_pipelines_cmd(input_file, input_dir, output_file, output_dir, db_name,
                           db_collection, combined_output, generate_matrix, address, prefix):
    """Compare results from new pipeline to old results."""
    if not input_file and not input_dir:
        raise click.UsageError("One of --input-file or --input-dir is required.")
    if input_file and input_dir:
        raise click.UsageError("--input-file and --input-dir are mutually exclusive.")
    if not output_file and not output_dir:
        raise click.UsageError("One of --output-file or --output-dir is required.")
    if output_file and output_dir:
        raise click.UsageError("--output-file and --output-dir are mutually exclusive.")
    options = types.SimpleNamespace(
        input_file=list(input_file) if input_file else None,
        input_dir=input_dir,
        output_file=output_file, output_dir=output_dir,
        db_name=db_name, db_collection=db_collection,
        combined_output=combined_output, generate_matrix=generate_matrix,
        address=address, prefix=prefix,
    )
    _parser().validate_pipelines(options)


@cli.command('identify-missing')
@click.option('-o', '--output-file', required=True, help='Path to output file')
@click.option('--db-name', required=True, help='MongoDB database name')
@click.option('--db-collection', required=True, help='MongoDB collection name')
@click.option('--analysis-dir', default=None,
              help='Analysis results dir containing JASEN results')
@click.option('--restore-dir', default='/fs2/seqdata/restored',
              help='Directory to restore spring files to')
@click.option('--restore-file', default=None, help='Filepath for bash restore script')
@click.option('--missing-log', default='missing_samples.log',
              help='File containing missing files')
@click.option('--assay', default='jasen-saureus-dev', help='Assay for JASEN to run')
@click.option('--platform', default='illumina', help='Sequencing platform')
@click.option('--sample-sheet', is_flag=True, default=False, help='Sample sheet input')
@click.option('--alter-sample-id', is_flag=True, default=False,
              help='Alter sample ID to be LIMS ID + sequencing run')
@click.option('-i', '--input-file', multiple=True, default=None, help='Input filepath(s)')
def identify_missing_cmd(output_file, db_name, db_collection, analysis_dir, restore_dir,
                         restore_file, missing_log, assay, platform, sample_sheet,
                         alter_sample_id, input_file):
    """Find missing sample data from old runs."""
    options = types.SimpleNamespace(
        output_file=output_file, db_name=db_name, db_collection=db_collection,
        analysis_dir=analysis_dir, restore_dir=restore_dir, restore_file=restore_file,
        missing_log=missing_log, assay=assay, platform=platform,
        sample_sheet=sample_sheet, alter_sample_id=alter_sample_id,
        input_file=list(input_file) if input_file else None,
    )
    _parser().identify_missing(options)


@cli.command('transform-file-format')
@click.option('-i', '--input-file', required=True, multiple=True,
              help='Path to targets TSV file')
@click.option('-o', '--output-file', required=True, help='Path to output file')
@click.option('-f', '--out-format', default='bed', help='Output format')
@click.option('-a', '--accession', default=None, help='Accession number')
def transform_file_format_cmd(input_file, output_file, out_format, accession):
    """Convert file format."""
    options = types.SimpleNamespace(
        input_file=list(input_file), output_file=output_file,
        out_format=out_format, accession=accession,
    )
    _parser().transform_file_format(options)


@cli.command('reformat-csv')
@click.option('--csv-file', required=True, help='Path to bjorn CSV file')
@click.option('-o', '--output-file', required=True, help='Path to fixed output CSV file')
@click.option('--sh-file', default=None, help='Path to bjorn SH file')
@click.option('--remote-dir', default='/fs1/bjorn/jasen',
              help='Remote directory for spring files')
@click.option('--remote-hostname', default='rs-fe1.lunarc.lu.se',
              help='Remote hostname')
@click.option('--remote', is_flag=True, default=False, help='Remote copy')
@click.option('--auto-start', is_flag=True, default=False,
              help='Automatically start')
@click.option('--alter-sample-id', is_flag=True, default=False,
              help='Alter sample ID to be LIMS ID + sequencing run')
def reformat_csv_cmd(csv_file, output_file, sh_file, remote_dir, remote_hostname,
                     remote, auto_start, alter_sample_id):
    """Fix bjorn microbiology CSV file."""
    options = types.SimpleNamespace(
        csv_file=csv_file, output_file=output_file, sh_file=sh_file,
        remote_dir=remote_dir, remote_hostname=remote_hostname,
        remote=remote, auto_start=auto_start, alter_sample_id=alter_sample_id,
    )
    _parser().reformat_csv(options)


@cli.command('converge-catalogues')
@click.option('--output-dir', default=None, help='Path to output directory')
@click.option('--save-dbs', is_flag=True, default=False,
              help='Save all intermediary DBs created for TBProfiler DB convergence')
def converge_catalogues_cmd(output_dir, save_dbs):
    """Converge TB mutation catalogues."""
    options = types.SimpleNamespace(output_dir=output_dir, save_dbs=save_dbs)
    _parser().converge_catalogues(options)


@cli.command('post-align-qc')
@click.option('--sample-id', required=True, help='Sample ID')
@click.option('--bam-file', required=True, help='Input BAM file')
@click.option('--reference', required=True, help='Reference FASTA file')
@click.option('-o', '--output-file', required=True, help='Path to QC JSON output file')
@click.option('--bed-file', default=None, help='Input BED file')
@click.option('--baits-file', default=None, help='Input baits file')
@click.option('--cpus', default=2, type=int, help='Number of CPUs')
def post_align_qc_cmd(sample_id, bam_file, reference, output_file, bed_file,
                      baits_file, cpus):
    """Run QC on BWA alignment."""
    options = types.SimpleNamespace(
        sample_id=sample_id, bam_file=bam_file, reference=reference,
        output_file=output_file, bed_file=bed_file, baits_file=baits_file, cpus=cpus,
    )
    _parser().post_align_qc(options)


@cli.command('count-reads')
@click.option('-i', '--input-file', required=True, multiple=True,
              help='Path to FASTQ file(s); provide R1 only or R1 + R2')
@click.option('-o', '--output-file', required=True, help='Path to JSON output file')
@click.option('--sample-id', default=None, help='Sample ID')
def count_reads_cmd(input_file, output_file, sample_id):
    """Count reads in FASTQ file(s)."""
    options = types.SimpleNamespace(
        input_file=list(input_file), output_file=output_file, sample_id=sample_id,
    )
    _parser().count_reads(options)
