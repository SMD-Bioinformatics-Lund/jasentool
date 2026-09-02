"""Command line interface module"""
# pylint: disable=too-many-arguments,too-many-positional-arguments

import types
import logging
from pathlib import Path

import click

from jasentool import __version__
from jasentool.log import setup_logging
from jasentool.main import OptionsParser


def _parser():
    return OptionsParser(__version__)


def _init_logging(verbose=False):
    """Configure logging to stdout. Subcommands call this as their first body line."""
    setup_logging(level=logging.DEBUG if verbose else logging.INFO)


@click.group()
@click.version_option(__version__)
def cli():
    """Multipurpose tool for the JASEN pipeline and Bonsai."""


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
    _init_logging()
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
    _init_logging()
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
    _init_logging()
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
    _init_logging()
    options = types.SimpleNamespace(
        input_file=list(input_file), output_file=output_file,
        out_format=out_format, accession=accession,
    )
    _parser().transform_file_format(options)


@cli.command('reformat-csv')
@click.option('-v', '--verbose', is_flag=True, default=False, help='Enable debug logging')
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
def reformat_csv_cmd(verbose, csv_file, output_file, sh_file, remote_dir, remote_hostname,
                     remote, auto_start, alter_sample_id):
    """Reformat bjorn microbiology CSV file."""
    _init_logging(verbose)
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
    _init_logging()
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
    _init_logging()
    options = types.SimpleNamespace(
        sample_id=sample_id, bam=bam_file,
        output_file=output_file, bed=bed_file, cpus=cpus,
    )
    _parser().post_align_qc(options)


@cli.command('count-reads')
@click.option('--fastq1', required=True, help='Path to R1 FASTQ file')
@click.option('--fastq2', default=None, help='Path to R2 FASTQ file (optional, paired-end)')
@click.option('-o', '--output-file', required=True, help='Path to JSON output file')
@click.option('--sample-id', default=None, help='Sample ID')
def count_reads_cmd(fastq1, fastq2, output_file, sample_id):
    """Count reads in FASTQ file(s)."""
    _init_logging()
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
    _init_logging()
    options = types.SimpleNamespace(
        accession=list(accession), output_dir=output_dir,
        bwa_index=bwa_index, fai_index=fai_index, clean=clean,
    )
    _parser().download_ncbi(options)


@cli.command('concatenate-files')
@click.option('-i', '--input', 'input_files', required=True, multiple=True,
              help='Input YAML file(s) to concatenate')
@click.option('-o', '--output-file', required=True, help='Path to output YAML file')
def concatenate_files_cmd(input_files, output_file):
    """Concatenate multiple YAML files (e.g. versions.yml) into one."""
    _init_logging()
    options = types.SimpleNamespace(input_files=list(input_files), output_file=output_file)
    _parser().concatenate_files(options)


@cli.command('create-yaml')
@click.option('--amrfinder', type=click.Path(), default=None)
@click.option('--bam', type=click.Path(), default=None)
@click.option('--bai', type=click.Path(), default=None)
@click.option('--chewbbaca', type=click.Path(), default=None)
@click.option('--emmtyper', type=click.Path(), default=None)
@click.option('--gambitcore', type=click.Path(), default=None)
@click.option('--groups', multiple=True, required=True)
@click.option('--kleborate', type=click.Path(), default=None)
@click.option('--kleborate-hamronization', type=click.Path(), default=None)
@click.option('--kraken', type=click.Path(), default=None)
@click.option('--lims-id', default=None)
@click.option('--mlst', type=click.Path(), default=None)
@click.option('--mykrobe', type=click.Path(), default=None)
@click.option('--nanoplot', type=click.Path(), default=None)
@click.option('--nextflow-run-info', type=click.Path(), default=None)
@click.option('--plasmidfinder', type=click.Path(), default=None)
@click.option('--plasmidfinder-genome-hits', type=click.Path(), default=None)
@click.option('--plasmidfinder-plasmid-seqs', type=click.Path(), default=None)
@click.option('--samtools-bedcov', type=click.Path(), default=None)
@click.option('--samtools-stats', type=click.Path(), default=None)
@click.option('--quast', type=click.Path(), default=None)
@click.option('--ref-genome-annotation', type=click.Path(), default=None)
@click.option('--ref-genome-sequence', type=click.Path(), default=None)
@click.option('--resfinder', type=click.Path(), default=None)
@click.option('--sample-id', required=True)
@click.option('--sample-name', required=True)
@click.option('--samtools', type=click.Path(), default=None)
@click.option('--sccmec', type=click.Path(), default=None)
@click.option('--serotypefinder', type=click.Path(), default=None)
@click.option('--shigapass', type=click.Path(), default=None)
@click.option('--shigatyper', type=click.Path(), default=None)
@click.option('--ska-index', type=click.Path(), default=None)
@click.option('--software-info', type=click.Path(), multiple=True)
@click.option('--sourmash-signature', type=click.Path(), default=None)
@click.option('--spatyper', type=click.Path(), default=None)
@click.option('--tb-grading-rules-bed', type=click.Path(), default=None)
@click.option('--tbdb-bed', type=click.Path(), default=None)
@click.option('--tbprofiler', type=click.Path(), default=None)
@click.option('--vcf', type=click.Path(), default=None)
@click.option('--versions', type=click.Path(), default=None)
@click.option('--virulencefinder', type=click.Path(), default=None)
@click.option('-o', '--output', required=True, type=click.Path())
def create_yaml_cmd(amrfinder, bam, bai, chewbbaca, emmtyper, gambitcore, groups,
                    kleborate, kleborate_hamronization, kraken, lims_id, mlst,
                    mykrobe, nanoplot, nextflow_run_info, plasmidfinder,
                    plasmidfinder_genome_hits, plasmidfinder_plasmid_seqs,
                    quast,
                    ref_genome_annotation, ref_genome_sequence, resfinder,
                    sample_id, sample_name, samtools, samtools_bedcov,
                    samtools_stats, sccmec, serotypefinder, shigapass,
                    shigatyper, ska_index, software_info, sourmash_signature,
                    spatyper, tb_grading_rules_bed, tbdb_bed, tbprofiler,
                    vcf, versions, virulencefinder, output):
    """Create YAML input file for Bonsai upload."""
    _init_logging()
    options = types.SimpleNamespace(
        amrfinder=amrfinder, bam=bam, bai=bai, chewbbaca=chewbbaca,
        emmtyper=emmtyper, gambitcore=gambitcore, groups=groups,
        kleborate=kleborate, kleborate_hamronization=kleborate_hamronization,
        kraken=kraken, lims_id=lims_id, mlst=mlst, mykrobe=mykrobe,
        nanoplot=nanoplot, nextflow_run_info=nextflow_run_info,
        plasmidfinder=plasmidfinder,
        plasmidfinder_genome_hits=plasmidfinder_genome_hits,
        plasmidfinder_plasmid_seqs=plasmidfinder_plasmid_seqs,
        quast=quast,
        ref_genome_annotation=ref_genome_annotation,
        ref_genome_sequence=ref_genome_sequence, resfinder=resfinder,
        sample_id=sample_id, sample_name=sample_name, samtools=samtools,
        samtools_bedcov=samtools_bedcov, samtools_stats=samtools_stats,
        sccmec=sccmec, serotypefinder=serotypefinder, shigapass=shigapass,
        shigatyper=shigatyper, ska_index=ska_index, software_info=software_info,
        sourmash_signature=sourmash_signature, spatyper=spatyper,
        tb_grading_rules_bed=tb_grading_rules_bed, tbdb_bed=tbdb_bed,
        tbprofiler=tbprofiler, vcf=vcf, versions=versions,
        virulencefinder=virulencefinder, output=output,
    )
    _parser().create_yaml(options)


@cli.command('format-cdm')
@click.argument('manifest', type=click.Path(exists=True, dir_okay=False))
@click.option('-o', '--output-file', default=None, help='Path to output file')
def format_cdm_cmd(manifest, output_file):
    """Build a CDM input file from a JASEN sample manifest (e.g. created by create-yaml)."""
    _init_logging()
    options = types.SimpleNamespace(manifest=manifest, output_file=output_file)
    _parser().format_cdm(options)


@cli.command('minority-report')
@click.option('--mpileup', required=True, type=click.Path(exists=True),
              help='Input mpileup file (.mpileup or .mpileup.gz)')
@click.option('--blacklist', default=None, type=click.Path(exists=True),
              help='Optional blacklist TSV file of positions to exclude')
@click.option('-o', '--output', required=True, help='Output path stem (no extension)')
def minority_report_cmd(mpileup, blacklist, output):
    """Compute minority base frequency distribution from a samtools mpileup file."""
    _init_logging()
    options = types.SimpleNamespace(mpileup=mpileup, blacklist=blacklist, output=output)
    _parser().minority_report(options)


@cli.command('create-blacklist')
@click.option('-v', '--verbose', is_flag=True, default=False, help='Enable debug logging')
@click.option('-i', '--input-file', default=None,
              help='Text file containing BAM file paths (one per line)')
@click.option('--input-dir', default=None,
              help='Directory containing *.bam files')
@click.option('--output-dir', required=True, help='Directory for intermediate files')
@click.option('-o', '--output-file', required=True, help='Path to the output blacklist TSV')
@click.option('--bed-file', default=None, type=click.Path(exists=True),
              help='BED file passed to samtools mpileup -l')
@click.option('--samtools', default='samtools', show_default=True,
              help='Path or name of the samtools executable')
@click.option('--sample-pattern', default='.*', show_default=True,
              help='Regex to filter sample names included in blacklist aggregation')
@click.option('--min-freq', default=0.05, show_default=True, type=float,
              help='Minimum minority frequency to count a position')
@click.option('--min-count', default=5, show_default=True, type=int,
              help='Minimum number of samples a position must appear in to enter the blacklist')
def create_blacklist_cmd(verbose, input_file, input_dir, output_dir, output_file,
                         bed_file, samtools, sample_pattern, min_freq, min_count):
    """Create a minority variant blacklist from a set of BAM files."""
    _init_logging(verbose)
    if not input_file and not input_dir:
        raise click.UsageError("One of --input-file or --input-dir is required.")
    if input_file and input_dir:
        raise click.UsageError("--input-file and --input-dir are mutually exclusive.")
    options = types.SimpleNamespace(
        input_file=input_file, input_dir=input_dir,
        output_dir=output_dir, output_file=output_file,
        bed_file=bed_file, samtools=samtools,
        sample_pattern=sample_pattern, min_freq=min_freq, min_count=min_count,
    )
    _parser().create_blacklist(options)


@cli.command('check-backup')
@click.option('--profile', required=True,
              help='JASEN profile name, e.g. staphylococcus_aureus')
@click.option('--backup-dir', required=True,
              type=click.Path(exists=True, file_okay=False),
              help='Root of the backup storage tree')
@click.option('--db-name', required=True,
              help='Bonsai MongoDB database name')
@click.option('--db-collection', required=True,
              help='Bonsai MongoDB collection name')
@click.option('--db-collection-groups', default='sample_group', show_default=True,
              help='Bonsai MongoDB collection holding sample_group docs')
@click.option('--address', '--uri', default='mongodb://localhost:27017/',
              help='Bonsai MongoDB address')
@click.option('--check-orphans', is_flag=True, default=False,
              help='After scanning, also list files in the backup tree that do '
                   'not match any expected <sample_id><mask><file_ext>')
@click.option('-o', '--output-file', required=True,
              help='Path to summary CSV; per-file missing CSV uses the same stem')
def check_backup_cmd(profile, backup_dir, db_name, db_collection, db_collection_groups,
                     address, check_orphans, output_file):
    """Cross-check Bonsai samples against the backup storage tree."""
    _init_logging()
    options = types.SimpleNamespace(
        profile=profile, backup_dir=backup_dir, db_name=db_name,
        db_collection=db_collection, db_collection_groups=db_collection_groups,
        address=address,
        check_orphans=check_orphans, output_file=output_file,
    )
    _parser().check_backup(options)


@cli.command('rebuild-manifests')
@click.option('--profile', required=True,
              help='JASEN profile name, e.g. staphylococcus_aureus')
@click.option('--backup-dir', required=True,
              type=click.Path(exists=True, file_okay=False),
              help='Root of the backup storage tree')
@click.option('--db-name', default=None,
              help='Bonsai MongoDB database name (required unless --no-bonsai)')
@click.option('--db-collection', default=None,
              help='Bonsai MongoDB collection name (required unless --no-bonsai)')
@click.option('--db-collection-groups', default='sample_group', show_default=True,
              help='Bonsai MongoDB collection holding sample_group docs')
@click.option('--address', '--uri', default='mongodb://localhost:27017/',
              help='Bonsai MongoDB address')
@click.option('--no-bonsai', is_flag=True, default=False,
              help='Discover samples by scanning the backup tree instead of querying Bonsai. '
                   'sample_name falls back to sample_id; lims_id and groups are left unset.')
@click.option('--sample-id', default=None,
              help='If set, only rebuild the manifest for this sample_id (e.g. to test on one '
                   'sample before a full run)')
@click.option('--versions-fallback', type=click.Path(exists=True, dir_okay=False), default=None,
              help='Flat YAML `software: version` map used to fill a version when the backup '
                   'tree has none (or only a _db version) for a tool. The tree always wins; '
                   'keys are the versions.yml software name (e.g. amrfinderplus, tb-profiler).')
@click.option('-o', '--output-dir', required=True, type=click.Path(),
              help='Directory to write <sample_id>_bonsai.yaml and <sample_id>_versions.yml')
def rebuild_manifests_cmd(profile, backup_dir, db_name, db_collection, db_collection_groups,
                          address, no_bonsai, sample_id, versions_fallback, output_dir):
    """Rebuild Bonsai manifest YAMLs (and merged versions.yml) from the backup storage tree."""
    _init_logging()
    if not no_bonsai and not (db_name and db_collection):
        raise click.UsageError(
            "--db-name and --db-collection are required unless --no-bonsai is set"
        )
    options = types.SimpleNamespace(
        profile=profile, backup_dir=backup_dir, db_name=db_name,
        db_collection=db_collection, db_collection_groups=db_collection_groups,
        address=address, no_bonsai=no_bonsai, sample_id=sample_id,
        versions_fallback=versions_fallback, output_dir=output_dir,
    )
    _parser().rebuild_manifests(options)


@cli.command('rerun-chewbbaca')
@click.option('--masked-assemblies', required=True, type=click.Path(),
              help='Path to _masked_assemblies.csv from `check-backup`')
@click.option('--schema-dir', required=True, type=click.Path(),
              help='chewBBACA schema directory (passed as --schema-directory)')
@click.option('--output-dir', required=True, type=click.Path(),
              help='Output directory; chewBBACA results land in <output-dir>/output_dir/, '
                   'batch list in <output-dir>/batch_input.list')
@click.option('--training-file', default=None, type=click.Path(),
              help='Optional chewBBACA training file (--ptf)')
@click.option('--cpus', default=4, show_default=True, type=int,
              help='chewBBACA --cpu value')
@click.option('--chewie-bin', default='chewie', show_default=True,
              help='Path or name of the chewie executable')
@click.option('--singularity-image', default=None, type=click.Path(),
              help='If set, wrap chewie invocation as `singularity exec <image> chewie ...`')
@click.option('--singularity-bind', default=None,
              help='Comma-separated bind list passed to `singularity exec --bind` '
                   '(e.g. "/media/isilon,/data,/scratch"). Only used with --singularity-image.')
@click.option('--profile-filter', default=None,
              help='If set, include only rows whose `profile` column matches this value')
def rerun_chewbbaca_cmd(masked_assemblies, schema_dir, output_dir, training_file,
                        cpus, chewie_bin, singularity_image, singularity_bind,
                        profile_filter):
    """Re-run chewBBACA AlleleCall on a check-backup masked-assemblies CSV."""
    _init_logging()
    options = types.SimpleNamespace(
        masked_assemblies=masked_assemblies, schema_dir=schema_dir,
        output_dir=output_dir, training_file=training_file,
        cpus=cpus, chewie_bin=chewie_bin, singularity_image=singularity_image,
        singularity_bind=singularity_bind, profile_filter=profile_filter,
    )
    _parser().rerun_chewbbaca(options)


@cli.command('compare-distances')
@click.option('-i', '--input', 'input_files', required=True, nargs=2,
              type=click.Path(exists=True, dir_okay=False),
              help='Two chewBBACA cgMLST allele-call TSVs (sample_id in column 1, loci '
                   'calls after); same sample names in both')
@click.option('-o', '--output-dir', required=True, type=click.Path(),
              help='Output directory for the two distance matrices and their difference')
@click.option('--mlst', default=None, type=click.Path(exists=True, dir_okay=False),
              help='Optional sample_name,mlst_st CSV/TSV; enables the missing-loci-vs-ST plot')
@click.option('--cgmlst-dists-bin', default='cgmlst-dists', show_default=True,
              help='Path or name of the cgmlst-dists executable (Python fallback if absent)')
@click.option('--min-mean-distance', default=None, type=float,
              help='Lower bound on the Bland-Altman mean-distance (x) axis for an extra '
                   'zoomed plot written alongside the full-range one')
@click.option('--max-mean-distance', default=None, type=float,
              help='Upper bound on the Bland-Altman mean-distance (x) axis for an extra '
                   'zoomed plot (e.g. 50 or 100, the clinically relevant band)')
@click.option('-v', '--verbose', is_flag=True, default=False,
              help='Verbose logging and write the underlying plot point tables (*_points.tsv) '
                   'so individual points can be checked by hand')
def compare_distances_cmd(input_files, output_dir, mlst, cgmlst_dists_bin,
                          min_mean_distance, max_mean_distance, verbose):
    """Build cgMLST distance matrices for two chewBBACA tables and their difference."""
    _init_logging(verbose)
    options = types.SimpleNamespace(
        file1=input_files[0], file2=input_files[1], output_dir=output_dir,
        mlst=mlst, cgmlst_dists_bin=cgmlst_dists_bin,
        min_mean_distance=min_mean_distance, max_mean_distance=max_mean_distance,
        verbose=verbose,
    )
    _parser().compare_distances(options)


@cli.command('annotate-delly')
@click.option('-v', '--vcf', required=True, type=click.Path(exists=True, path_type=Path),
              help='Delly VCF/BCF to annotate')
@click.option('-b', '--bed', required=True, type=click.Path(exists=True, path_type=Path),
              help='Tabix-indexed BED file with gene annotations')
@click.option('-o', '--output', required=True, type=click.Path(writable=True, path_type=Path),
              help='Output annotated VCF path')
def annotate_delly_cmd(vcf, bed, output):
    """Annotate Delly structural variants with gene and locus_tag from a BED file."""
    _init_logging()
    options = types.SimpleNamespace(vcf=vcf, bed=bed, output=output)
    _parser().annotate_delly(options)


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
    _init_logging()
    options = types.SimpleNamespace(
        url=url, site=site, key_name=key_name, output_dir=output_dir,
        token_dir=token_dir, db=db, setup=setup, download_scheme=download_scheme,
        force=force, cron=cron, method=method, output_file=output_file,
    )
    _parser().download_bigsdb(options)
