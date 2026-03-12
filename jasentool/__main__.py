"""__main__ file that handles help and cli execution"""

import logging
import sys

from jasentool import __author__, __copyright__, __version__
from jasentool.cli import get_main_parser
from jasentool.log import get_logger, setup_logging
from jasentool.main import OptionsParser

logger = get_logger(__name__)

def print_help():
    """Print help string for jasentool software"""
    print(f'''

                    ...::: Jasentool v{__version__} :::...
Author(s): {__author__}

Description:
    This software is a mongodb tool that fetches, inserts and
    removes specific sample data. Furthermore, it validates new
    pipeline data against that of the old data stored in mongodb
    database.

Usage: jasentool <method> <options>

Information:
    -V, --version       Display the version of Jasentool and exit.
    -h,  --help         Print help.

Methods:
    find                    Find samples in given db.
    identify-missing        Find data missing from Bonsai compared to cgviz.
    validate-pipelines      Compare new pipeline data with old data.
    transform-file-format   Convert cgmlst.org target files to bed files.
    reformat-csv            Fix output files from bjorn.
    converge-catalogues     Converge tuberculosis mutation catlogues.
    post-align-qc           Extract QC values after alignment.
    count-reads             Count reads in FASTQ file(s).
''')

def main():
    """Main function that handles cli"""
    setup_logging()
    if len(sys.argv) == 1:
        print_help()
        sys.exit(0)
    elif sys.argv[1] in {'-V', '--version'}:
        print(f"Jasentool version {__version__} {__copyright__} {__author__}")
        sys.exit(0)
    elif sys.argv[1] in {'-h', '--h', '-help', '--help'}:
        print_help()
        sys.exit(0)
    else:
        try:
            args = get_main_parser().parse_args()
            if args.verbose:
                logging.getLogger().setLevel(logging.DEBUG)
            ts_parser = OptionsParser(__version__)
            ts_parser.parse_options(args)
            logger.info("Done")
        except SystemExit as exc:
            if exc.code != 0:
                logger.error('Controlled exit resulting from early termination.')
            sys.exit(exc.code)
        except KeyboardInterrupt:
            logger.warning('Controlled exit resulting from interrupt signal.')
            sys.exit(1)
        except Exception as error_code:
            logger.exception('Uncontrolled exit resulting from an unexpected error: %s', error_code)
            sys.exit(1)

if __name__ == "__main__":
    main()
