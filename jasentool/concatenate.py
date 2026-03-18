"""Module for concatenating YAML files"""
import yaml
from jasentool.log import get_logger

logger = get_logger(__name__)

class Concatenate:
    @staticmethod
    def run(input_files, output_file):
        merged = {}
        for input_file in input_files:
            with open(input_file, 'r', encoding="utf-8") as fin:
                data = yaml.safe_load(fin)
                if data:
                    merged.update(data)
        with open(output_file, 'w', encoding="utf-8") as fout:
            yaml.dump(merged, fout, default_flow_style=False)
        logger.info("Concatenated %d files to %s", len(input_files), output_file)
