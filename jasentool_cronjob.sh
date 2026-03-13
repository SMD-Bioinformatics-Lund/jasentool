#!/bin/bash
#
# Disclaimer:
#   This script is intended exclusively for use by the Section for Molecular
#   Diagnostics, Region Skåne, Lund, Sweden. It monitors for new sequencing runs, 
#   adjusts the csv to suit JASEN formatting, and automatically submits them
#   to the JASEN pipeline. It should not be run manually in production
#   environments outside of that context.
#
# Cron usage:
#   This script is designed to be executed every 5 minutes via cron.
#   Add the following entry with `crontab -e`:
#
#     */5 * * * * /path/to/jasentool_cronjob.sh 2>&1
#
#   Ensure the CRONDIR environment variable is set in the cron environment,
#   or update the default path in this script before deploying.

CURRENT_DATE=$(date +"%y%m%d")
SEARCH_PATH="/fs2/seqdata/NovaSeq/*/pipeline/multi_microbiology.csv"
CRONDIR="${CRONDIR:-/data/bnf/dev/ryan/jobs/cron}"

cd $CRONDIR
NEW_SAUREUS_CSV=$(find $SEARCH_PATH -type f -mmin -60 2>/dev/null)
if [[ -n "$NEW_SAUREUS_CSV" ]]; then
echo "New file detected: $NEW_SAUREUS_CSV" >> ${CRONDIR}/saureus_cronjob.log
SEQUENCING_RUN=$(head -2 $NEW_SAUREUS_CSV | tail -1 | cut -d',' -f7 | cut -d'/' -f5)
conda run -n jasentool jasentool reformat-csv --csv_file $NEW_SAUREUS_CSV --sh_file "${NEW_SAUREUS_CSV%.csv}.sh" -o ${SEQUENCING_RUN}_jasen_cron.csv --remote_dir /fs1/ryan/jasen/bjorn/ --remote --auto_start --alter_sample_id
fi
