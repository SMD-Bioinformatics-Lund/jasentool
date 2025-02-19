#!/bin/bash


RERUNSDIR=/data/bnf/dev/ryan/pipelines/jasen/reruns
CRONDIR=/data/bnf/dev/ryan/jobs/cron
CURRENT_DATE=$(date +"%y%m%d")
DEST_HOST="rs-fe1.lunarc.lu.se"

if [ "$1" == "missing" ]; then
  cd $RERUNSDIR
  conda run -n jasentool jasentool missing --db_name cgviz --db_collection sample --analysis_dir /fs1/results_dev/jasen/saureus/analysis_result/ --restore_dir /fs1/ryan/jasen/reruns/seqdata/ --missing_log ${RERUNSDIR}/saureus_${CURRENT_DATE}_missing_reads.log --restore_file ${RERUNSDIR}/saureus_${CURRENT_DATE}.sh -o ${RERUNSDIR}/saureus_${CURRENT_DATE}.csv --alter_sample_id
  scp ${RERUNSDIR}/saureus_${CURRENT_DATE}.csv ${DEST_HOST}:/fs1/ryan/jasen/bjorn/${CURRENT_DATE}_jasen_missing.csv
  ssh ${DEST_HOST} /fs2/sw/bnf-scripts/start_nextflow_analysis_dev.pl /fs1/ryan/jasen/bjorn/${CURRENT_DATE}_jasen_missing.csv
else
  cd $CRONDIR
  SEARCH_PATH="/fs2/seqdata/NovaSeq/*/pipeline/multi_microbiology.csv"
  NEW_SAUREUS_CSV=$(find $SEARCH_PATH -type f -mmin -60 2>/dev/null)
  if [[ -n "$NEW_SAUREUS_CSV" ]]; then
    echo "New file detected: $NEW_SAUREUS_CSV" >> ${CRONDIR}/saureus_cronjob.log
    SEQUENCING_RUN=$(head -2 $NEW_SAUREUS_CSV | tail -1 | cut -d',' -f7 | cut -d'/' -f5)
    conda run -n jasentool jasentool fix --csv_file $NEW_SAUREUS_CSV --sh_file "${NEW_SAUREUS_CSV%.csv}.sh" -o ${SEQUENCING_RUN}_jasen_cron.csv --remote_dir /fs1/ryan/jasen/bjorn/ --remote --auto_start --alter_sample_id
  fi
fi
