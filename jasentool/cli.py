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
    """Transform file format from cgmlst.org target file to bed file."""
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
    """Reformat bjorn microbiology CSV file."""
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
@click.option('-o', '--output-file', required=True, help='Path to QC JSON output file')
@click.option('--bed-file', default=None, help='Input BED file')
@click.option('--cpus', default=2, type=int, help='Number of CPUs')
def post_align_qc_cmd(sample_id, bam_file, output_file, bed_file, cpus):
    """Run QC on BWA alignment."""
    options = types.SimpleNamespace(
        sample_id=sample_id, bam_file=bam_file,
        output_file=output_file, bed_file=bed_file, cpus=cpus,
    )
    _parser().post_align_qc(options)


@cli.command('count-reads')
@click.option('--fastq1', required=True, help='Path to R1 FASTQ file')
@click.option('--fastq2', default=None, help='Path to R2 FASTQ file (optional, paired-end)')
@click.option('-o', '--output-file', required=True, help='Path to JSON output file')
@click.option('--sample-id', default=None, help='Sample ID')
def count_reads_cmd(fastq1, fastq2, output_file, sample_id):
    """Count reads in FASTQ file(s)."""
    input_files = [fastq1] if fastq2 is None else [fastq1, fastq2]
    options = types.SimpleNamespace(
        input_file=input_files, output_file=output_file, sample_id=sample_id,
    )
    _parser().count_reads(options)


@cli.command('download-ncbi')
@click.option('-i', '--accession', required=True, multiple=True,
              help='NCBI accession number(s)')
@click.option('-o', '--output-dir', required=True, help='Output directory')
@click.option('--bwa-index', is_flag=True, default=False, help='Run bwa index')
@click.option('--fai-index', is_flag=True, default=False, help='Run samtools faidx')
@click.option('--clean', is_flag=True, default=False,
              help='Clear output directory before download')
def download_ncbi_cmd(accession, output_dir, bwa_index, fai_index, clean):
    """Download genome FASTA and GFF from NCBI Datasets v2 API."""
    options = types.SimpleNamespace(
        accession=list(accession), output_dir=output_dir,
        bwa_index=bwa_index, fai_index=fai_index, clean=clean,
    )
    _parser().download_ncbi(options)


@cli.command('download-bigsdb')
@click.option('--url', default=None, help='API endpoint URL')
@click.option('--site', type=click.Choice(['PubMLST', 'Pasteur']), default=None,
              help='BIGSdb site')
@click.option('--key-name', required=True, help='API key name (unique per site)')
@click.option('--output-dir', default=None,
              help='Directory for per-locus FASTA files (--download-scheme)')
@click.option('--token-dir', default='./.bigsdb_tokens', show_default=True,
              help='Token storage directory')
@click.option('--db', default=None, help='Database config (setup only)')
@click.option('--setup', is_flag=True, default=False, help='Initial OAuth1 setup')
@click.option('--download-scheme', is_flag=True, default=False,
              help='Download all scheme loci')
@click.option('--force', is_flag=True, default=False,
              help='Re-download existing files (--download-scheme)')
@click.option('--cron', is_flag=True, default=False,
              help='Non-interactive / cron mode')
@click.option('--method', type=click.Choice(['GET', 'POST']), default='GET',
              show_default=True, help='HTTP method')
@click.option('--output-file', default=None, help='Save single response to this file')
def download_bigsdb_cmd(url, site, key_name, output_dir, token_dir, db, setup,
                        download_scheme, force, cron, method, output_file):
    """Download cgMLST scheme alleles from PubMLST or BIGSdb Pasteur via OAuth1."""
    options = types.SimpleNamespace(
        url=url, site=site, key_name=key_name, output_dir=output_dir,
        token_dir=token_dir, db=db, setup=setup, download_scheme=download_scheme,
        force=force, cron=cron, method=method, output_file=output_file,
    )
    _parser().download_bigsdb(options)


@cli.command('download-krakendb')
@click.option('-o', '--output-dir', required=True,
              help='Output directory for DB and genomes')
@click.option('--db-name', default='HumanViralBacteria', show_default=True,
              help='Kraken2 database name')
@click.option('--threads', default=4, type=int, show_default=True,
              help='Threads for kraken2-build')
def download_krakendb_cmd(output_dir, db_name, threads):
    """Build a Kraken2 database from NCBI RefSeq human, bacterial, and viral genomes."""
    options = types.SimpleNamespace(
        output_dir=output_dir, db_name=db_name, threads=threads,
    )
    _parser().download_krakendb(options)
