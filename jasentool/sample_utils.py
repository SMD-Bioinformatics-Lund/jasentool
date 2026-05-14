"""Helpers shared across subcommands that resolve sample identifiers
and scan filesystem layouts (analysis results, backup storage, etc.)."""

import os
import re
import json
from jasentool.log import get_logger

logger = get_logger(__name__)


def alter_sample_id(lims_id, sequencing_run):
    """Compose the canonical alter-sample-id form: <lims>_<seqrun> lowercased."""
    return f"{lims_id.lower()}_{sequencing_run.lower()}"


def find_files(search_term, parent_dir):
    """Find files in a given directory using a regex search term."""
    if not os.path.exists(parent_dir):
        logger.warning("%s does not exist! Skipping search.", parent_dir)
        return []
    try:
        search_files = os.listdir(parent_dir)
        return sorted(
            os.path.join(parent_dir, search_file) for search_file in search_files
            if re.search(search_term, search_file) and not search_file.endswith("~")
        )
    except Exception as exc:
        logger.error("Could not list files in %s: %s", parent_dir, exc)
        return []


def check_format(fpath):
    """Rewrite stale `/fs1`/`/fs2`/`NovaSeq` path prefixes to the current backing store."""
    if (
        fpath.startswith("/fs1")
        and not os.path.exists(os.path.join(fpath, "Data/Intensities/BaseCalls"))
    ):
        logger.warning("%s does not exist! Fixing by removing '/fs1' prefix.", fpath)
        fpath = fpath.replace("/fs1", "")
    if (
        fpath.startswith("/fs2")
        and not os.path.exists(os.path.join(fpath, "Data/Intensities/BaseCalls"))
    ):
        logger.warning("%s does not exist! Fixing by removing '/fs2' prefix.", fpath)
        fpath = fpath.replace("/fs2", "")
    if fpath.startswith("NovaSeq"):
        fpath = "/seqdata/" + fpath
        logger.warning("%s does not exist! Fixing by adding '/seqdata/' as a prefix.", fpath)
    if not fpath.startswith("/data"):
        fs2_fpath = "/fs2" + fpath
        isilon_fpath = "/media/isilon/backup_hopper" + fpath
        data_fpath = "/data" + fpath
        if os.path.exists(os.path.join(fs2_fpath, "Data/Intensities/BaseCalls")):
            return fs2_fpath
        if os.path.exists(os.path.join(isilon_fpath, "Data/Intensities/BaseCalls")):
            return isilon_fpath
        if os.path.exists(os.path.join(data_fpath, "Data/Intensities/BaseCalls")):
            return data_fpath
        if os.path.exists(fpath):
            return fpath.rstrip("Data/Intensities/BaseCalls/")
        logger.warning("Base calls for %s cannot be found.", fpath)
    return fpath


def get_sample_name(json_fpath):
    """Read a result JSON and return its `sample_name`, or None on failure."""
    try:
        with open(json_fpath, 'r', encoding="utf-8") as fin:
            result_json = json.load(fin)
        return result_json["sample_name"]
    except KeyError as exc:
        logger.error("KeyError: %s %s", exc, json_fpath)
        return None
    except json.JSONDecodeError:
        logger.error("JSONDecodeError: %s", json_fpath)
        return None


def parse_dir(dir_fpath, alter_sample_id_flag):
    """List sample identifiers from a JASEN results directory of `*.json` files."""
    dir_fpaths = []
    for filename in os.listdir(dir_fpath):
        if filename.endswith(".json"):
            if alter_sample_id_flag:
                sample_name = get_sample_name(os.path.join(dir_fpath, filename))
                if sample_name:
                    dir_fpaths.append(sample_name)
            else:
                dir_fpaths.append(filename.split("_")[0])
    return dir_fpaths


def filter_by_keys(source_dict, keys):
    """Return (filtered_dict, not_found_list) for the requested keys."""
    filtered = {}
    not_found = []
    for key in keys:
        try:
            filtered[key] = source_dict[key]
        except KeyError:
            not_found.append(key)
    logger.info("%d samples could not be found", len(not_found))
    logger.info("%d samples remain after filtering", len(filtered))
    return filtered, not_found
