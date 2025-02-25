"""Module for validating pipelines"""

import os
import sys
import json
import numpy as np
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from jasentool.database import Database

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

    def compare_cgmlst_alleles(self, row_cgmlst_alleles, col_cgmlst_alleles):
        """Parse through cgmlst alleles of old and new pipeline and compare results"""
        mismatch_count = 0
        null_values = ["-", "EXC", "INF", "LNF", "PLNF", "PLOT3", "PLOT5", "LOTSC", "NIPH", "NIPHEM", "PAMA", "ASM", "ALM"]
        for idx, row_allele in enumerate(row_cgmlst_alleles):
            col_allele = col_cgmlst_alleles[idx]
            if row_allele in null_values or col_allele in null_values:
                continue
            try:
                if int(row_allele) != int(col_allele):
                    mismatch_count += 1
            except ValueError:
                print(f"One following alleles are not in integer format: {row_allele} (row) or {col_allele} (column)")
        return mismatch_count
    
    def generate_matrix(self, sample_ids, get_cgmlst_data):
        matrix_df = pd.DataFrame(index=sample_ids, columns=sample_ids)
        id_allele_dict = {sample_id: get_cgmlst_data(sample_id) for sample_id in sample_ids}
        print(f"The sample id - alleles dict is approximately {sys.getsizeof(id_allele_dict)} bytes in size")
        for row_sample in sample_ids:
            row_sample_cgmlst = id_allele_dict[row_sample]
            for col_sample in sample_ids:
                col_sample_cgmlst = id_allele_dict[col_sample]
                if row_sample_cgmlst and col_sample_cgmlst:
                    matrix_df.loc[row_sample, col_sample] = self.compare_cgmlst_alleles(row_sample_cgmlst, col_sample_cgmlst)
        return matrix_df
    
    def plot_heatmap(self, distance_df, output_plot_fpath):
        plt.figure(figsize=(10, 8))
        sns.heatmap(distance_df, annot=True, cmap="coolwarm", center=0)
        plt.title("Differential Matrix Heatmap of cgmlst")
        plt.xlabel("Jasen")
        plt.ylabel("Cgviz")
        plt.savefig(output_plot_fpath, dpi=600)

    def plot_matrix_boxplot(self, df, output_plot_fpath):
        plt.figure(figsize=(10, 8))
        counts = list(df["sum"])
        sample_ids = list(df["SampleID"])
        plt.boxplot(counts)

        # Add jittered data points
        jitter = 0.04  # Adjust the jitter as needed
        x_jitter = np.random.normal(1, jitter, size=len(counts))
        plt.scatter(x_jitter, counts, alpha=0.5, color="blue")

        # Set labels and title
        plt.xlabel("Samples")
        plt.ylabel("Sum of sample allele differences")
        plt.title("Summed differential matrix of distances between pipelines' cgMLST results")

        # Annotate outliers
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
        # heatmap_fpath = os.path.join(os.path.dirname(output_fpaths[0]), "cgviz_vs_jasen_heatmap.png")
        output_csv_fpath = os.path.join(os.path.dirname(output_fpaths[0]), "cgviz_vs_jasen.csv")
        boxplot_matrix_fpath = os.path.join(os.path.dirname(output_fpaths[0]), "summed_differential_matrix_boxplot.png")
        sample_ids = [os.path.basename(input_file).replace("_result.json", "") for input_file in input_files]
        cgviz_matrix_df = self.generate_matrix(sample_ids, self.get_cgviz_cgmlst_data)
        jasen_matrix_df = self.generate_matrix(sample_ids, self.get_jasen_cgmlst_data)
        distance_df = jasen_matrix_df - cgviz_matrix_df
        distance_df = distance_df.astype(float)
        distance_df.to_csv(output_csv_fpath, index=True, header=True)
        # self.plot_heatmap(distance_df, output_plot_fpath)
        if os.path.exists(output_csv_fpath):
            distance_df = pd.read_csv(output_csv_fpath, index_col=0)
            distance_df["sum"] = distance_df.sum(axis=1)
            distance_df = distance_df.reset_index()
            distance_df.rename(columns={'index': 'SampleID'}, inplace=True)
            filtered_df = distance_df[["SampleID", "sum"]]
            self.plot_matrix_boxplot(filtered_df, boxplot_matrix_fpath)
