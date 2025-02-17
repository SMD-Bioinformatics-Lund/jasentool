#!/bin/bash

if [ "$1" == "missing" ]; then
  CURRENT_DATE=$(date +"%y%m%d")
  conda run -n jasentool jasentool missing --db_name cgviz --db_collection sample --analysis_dir /fs1/results_dev/jasen/saureus/analysis_result/ --restore_dir /fs1/ryan/jasen/reruns/seqdata/ --restore_file /data/bnf/dev/ryan/pipelines/jasen/reruns/saureus_${CURRENT_DATE}.sh -o /data/bnf/dev/ryan/pipelines/jasen/reruns/saureus_${CURRENT_DATE}.csv
  SEQUENCING_RUN=$(head -2 /data/tmp/multi_microbiology.csv | tail -1 | cut -d',' -f7 | cut -d'/' -f5)
  conda run -n jasentool jasentool fix --csv_file /data/bnf/dev/ryan/pipelines/jasen/reruns/saureus_${CURRENT_DATE}.csv --sh_file /data/bnf/dev/ryan/pipelines/jasen/reruns/saureus_${CURRENT_DATE}.sh -o ${SEQUENCING_RUN}_jasen.csv --remote_dir /fs1/ryan/jasen/bjorn/ --remote --auto-start --alter_sample_id
else
  SEARCH_PATH="/fs2/seqdata/NovaSeq/*/pipeline/multi_microbiology.csv"
  NEW_SAUREUS_CSV=$(find $SEARCH_PATH -type f -mmin -60 2>/dev/null)
  if [[ -n "$NEW_SAUREUS_CSV" ]]; then
    echo "New file detected: $NEW_SAUREUS_CSV" >> /data/bnf/dev/ryan/saureus_cronjob.log
    SEQUENCING_RUN=$(head -2 $NEW_SAUREUS_CSV | tail -1 | cut -d',' -f7 | cut -d'/' -f5)
    conda run -n jasentool jasentool fix --csv_file $NEW_SAUREUS_CSV --sh_file "${NEW_SAUREUS_CSV%.csv}.sh" -o ${SEQUENCING_RUN}_jasen.csv --remote_dir /fs1/ryan/jasen/bjorn/ --remote --auto_start --alter_sample_id
  fi
fi
