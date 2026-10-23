"""Module for validating pipelines"""

import os
import json
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache

import numpy as np
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from jasentool.database import Database
from jasentool.log import get_logger

logger = get_logger(__name__)

class Matrix:
    """Class to validate old pipeline (cgviz) with new pipeline (jasen)"""
    def __init__(self, input_dir, db_collection):
        self.input_dir = input_dir
        self.db_collection = db_collection

    def search(self, search_query, search_kw, search_list):
        """Search for query in list of arrays"""
        return [element for element in search_list if element[search_kw] == search_query]

    def get_cgviz_cgmlst_data(self, sample_id):
        """Get sample mongodb data"""
        mdb_cgmlst = list(Database.get_cgmlst(self.db_collection, {"id": sample_id, "metadata.QC": "OK"}))
        try:
            mdb_cgmlst_alleles = mdb_cgmlst[0]["alleles"]
            return mdb_cgmlst_alleles
        except IndexError:
            print(f"IndexError re sample {sample_id}")
            return False

    def get_jasen_cgmlst_data(self, sample_id):
        """Get sample input file data"""
        input_file = os.path.join(self.input_dir, sample_id + "_result.json")
        with open(input_file, 'r', encoding="utf-8") as fin:
            sample_json = json.load(fin)
            jasen_cgmlst = self.search("cgmlst", "type", sample_json["typing_result"])
            jasen_cgmlst_alleles = list(jasen_cgmlst[0]["result"]["alleles"].values())
        return jasen_cgmlst_alleles

    @staticmethod
    @lru_cache(maxsize=None)
    def _parse_allele(call):
        """Return the integer allele, or None if missing.

        Mirrors cgmlst-dists: chewBBACA inferred alleles `INF-<n>` count as allele
        `<n>`; every other non-integer (`-`, `LNF`, `NIPH`, `PLOT3`, `PLOT5`,
        `ASM`, ...) is treated as missing.
        """
        value = call[4:] if isinstance(call, str) and call.startswith("INF-") else call
        try:
            return abs(int(value))
        except (ValueError, TypeError):
            return None

    @staticmethod
    def compare_cgmlst_alleles(row_cgmlst_alleles, col_cgmlst_alleles):
        """Count loci where both samples have a valid allele and the alleles differ."""
        mismatch_count = 0
        for idx, row_allele in enumerate(row_cgmlst_alleles):
            row = Matrix._parse_allele(row_allele)
            col = Matrix._parse_allele(col_cgmlst_alleles[idx])
            if row is None or col is None:
                continue
            if row != col:
                mismatch_count += 1
        return mismatch_count

    @staticmethod
    def encode_alleles(allele_lists):
        """Integer array of equal-length allele lists, with -1 where a call is missing."""
        def parse(call):
            value = Matrix._parse_allele(call)
            return -1 if value is None else value
        return np.array([[parse(call) for call in alleles] for alleles in allele_lists],
                        dtype=np.int64)

    @staticmethod
    def distance_array(alleles, threads=1):
        """Per pair of rows, count loci where both have an allele and the alleles differ."""
        valid = alleles >= 0
        n_samples = len(alleles)
        dist = np.zeros((n_samples, n_samples), dtype=np.int64)

        def fill(rows):
            for i in rows:
                mismatch = (alleles[i] != alleles[i + 1:]) & valid[i] & valid[i + 1:]
                dist[i, i + 1:] = mismatch.sum(axis=1)

        threads = max(1, threads)
        with ThreadPoolExecutor(max_workers=threads) as pool:
            list(pool.map(fill, [range(start, n_samples, threads) for start in range(threads)]))
        return dist + dist.T

    @staticmethod
    def generate_matrix(sample_ids, get_cgmlst_data, threads=1):
        """Pairwise cgMLST distance matrix; NaN for samples without allele data."""
        id_allele_dict = {sample_id: get_cgmlst_data(sample_id) for sample_id in sample_ids}
        present = [sid for sid in sample_ids if id_allele_dict[sid]]
        if len({len(id_allele_dict[sid]) for sid in present}) > 1:
            raise ValueError("cgMLST allele lists differ in length between samples")
        dist = Matrix.distance_array(
            Matrix.encode_alleles([id_allele_dict[sid] for sid in present]), threads)
        if len(present) == len(sample_ids):
            return pd.DataFrame(dist, index=sample_ids, columns=sample_ids)
        matrix_df = pd.DataFrame(np.nan, index=sample_ids, columns=sample_ids)
        matrix_df.loc[present, present] = dist
        return matrix_df

    def plot_heatmap(self, distance_df, output_plot_fpath):
        """Plot heatmap"""
        plt.figure(figsize=(10, 8))
        sns.heatmap(distance_df, annot=True, cmap="coolwarm", center=0)
        plt.title("Differential Matrix Heatmap of cgmlst")
        plt.xlabel("Jasen")
        plt.ylabel("Cgviz")
        plt.savefig(output_plot_fpath, dpi=600)

    def plot_matrix_boxplot(self, df, output_plot_fpath):
        """Plot boxplot of matrix"""
        plt.figure(figsize=(10, 8))
        counts = list(df["sum"])
        sample_ids = list(df["SampleID"])
        plt.boxplot(counts)

        jitter = 0.04
        x_jitter = np.random.normal(1, jitter, size=len(counts))
        plt.scatter(x_jitter, counts, alpha=0.5, color="blue")

        plt.xlabel("Samples")
        plt.ylabel("Sum of sample allele differences")
        plt.title("Summed differential matrix of distances between pipelines' cgMLST results")

        for i, count in enumerate(counts):
            if count > 250000 or count < -750000:
                if float(x_jitter[i]) < 1:
                    plt.annotate(f"{sample_ids[i]}", xy=(x_jitter[i] - 0.01, count), xytext=(x_jitter[i] - 0.01, count),
                                horizontalalignment="right", fontsize=8)
                else:
                    plt.annotate(f"{sample_ids[i]}", xy=(x_jitter[i] - 0.01, count), xytext=(x_jitter[i] + 0.01, count),
                                horizontalalignment="left", fontsize=8)

        plt.tight_layout()
        plt.savefig(output_plot_fpath, dpi=600)

    def run(self, input_files, output_fpaths):
        """Run the matrix analyses"""
        output_csv_fpath = os.path.join(os.path.dirname(output_fpaths[0]), "cgviz_vs_jasen.csv")
        boxplot_matrix_fpath = os.path.join(os.path.dirname(output_fpaths[0]), "summed_differential_matrix_boxplot.png")
        sample_ids = [os.path.basename(input_file).replace("_result.json", "") for input_file in input_files]
        cgviz_matrix_df = self.generate_matrix(sample_ids, self.get_cgviz_cgmlst_data)
        jasen_matrix_df = self.generate_matrix(sample_ids, self.get_jasen_cgmlst_data)
        distance_df = jasen_matrix_df - cgviz_matrix_df
        distance_df = distance_df.astype(float)
        distance_df.to_csv(output_csv_fpath, index=True, header=True)
        if os.path.exists(output_csv_fpath):
            distance_df = pd.read_csv(output_csv_fpath, index_col=0)
            distance_df["sum"] = distance_df.sum(axis=1)
            distance_df = distance_df.reset_index()
            distance_df.rename(columns={'index': 'SampleID'}, inplace=True)
            filtered_df = distance_df[["SampleID", "sum"]]
            self.plot_matrix_boxplot(filtered_df, boxplot_matrix_fpath)
