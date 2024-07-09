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
    
    def get_null_allele_counts(self, input_files):
        """Get null position counts"""
        null_alleles_count = {}
        sample_null_count = {}
        for input_file in input_files:
            sample_id = os.path.basename(input_file).replace("_result.json", "")
            sample_null_count[sample_id] = 0
            with open(input_file, 'r', encoding="utf-8") as fin:
                sample_json = json.load(fin)
                jasen_cgmlst = self.search("cgmlst", "type", sample_json["typing_result"])
                jasen_cgmlst_alleles = dict(jasen_cgmlst[0]["result"]["alleles"])
                for allele in jasen_cgmlst_alleles:
                    if type(jasen_cgmlst_alleles[allele]) == str:
                        sample_null_count[sample_id] += 1
                        if allele in null_alleles_count:
                            null_alleles_count[allele] += 1
                        else:
                            null_alleles_count[allele] = 1
        print(f"The average number of missing alleles per sample is {sum(sample_null_count.values()) / len(sample_null_count.values())}")
        return null_alleles_count

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
        # null_values = ["-", "EXC", "INF", "LNF", "PLNF", "PLOT3", "PLOT5", "LOTSC", "NIPH", "NIPHEM", "PAMA"]
        # row_cgmlst_alleles = [int(allele) if allele not in null_values else np.nan for allele in row_cgmlst_alleles]
        # col_cgmlst_alleles = [int(allele) if allele not in null_values else np.nan for allele in col_cgmlst_alleles]

        row_cgmlst_alleles = np.array(row_cgmlst_alleles, dtype=object)
        col_cgmlst_alleles = np.array(col_cgmlst_alleles, dtype=object)

        # Convert None to np.nan
        row_cgmlst_alleles = np.where(row_cgmlst_alleles == "-", np.nan, row_cgmlst_alleles)
        col_cgmlst_alleles = np.where(col_cgmlst_alleles == "-", np.nan, col_cgmlst_alleles)

        # Convert arrays to numeric, coercing errors to np.nan
        row_cgmlst_alleles = pd.to_numeric(row_cgmlst_alleles, errors='coerce')
        col_cgmlst_alleles = pd.to_numeric(col_cgmlst_alleles, errors='coerce')

        # Identify positions with NaNs in either array
        nan_positions = np.isnan(row_cgmlst_alleles) | np.isnan(col_cgmlst_alleles)

        # Calculate mismatches excluding positions with NaNs
        mismatches = (row_cgmlst_alleles != col_cgmlst_alleles) & ~nan_positions
        mismatch_count = np.sum(mismatches)
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
        sns.heatmap(distance_df, annot=True, cmap='coolwarm', center=0)
        plt.title("Differential Matrix Heatmap of cgmlst")
        plt.xlabel("Jasen")
        plt.ylabel("Cgviz")
        plt.savefig(output_plot_fpath, dpi=600)

    def plot_barplot(self, count_dict, output_plot_fpath):
        categories = list(count_dict.keys())
        counts = list(count_dict.values())

        plt.figure(figsize=(10, 5))
        bars = plt.bar(categories, counts, color='skyblue')

        # Add titles and labels
        plt.xlabel('Alleles')
        plt.ylabel('Count')
        plt.title('Null Allele Count Bar Plot')

        # Add value labels on top of the bars
        for bar in bars:
            yval = bar.get_height()
            plt.text(bar.get_x() + bar.get_width()/2, yval + 1, yval, ha='center', va='bottom')

        plt.savefig(output_plot_fpath, dpi=600)
    
    def run(self, input_files, output_fpaths):
        output_csv_fpath = os.path.join(os.path.dirname(output_fpaths[0]), "cgviz_vs_jasen.csv")
        # heatmap_fpath = os.path.join(os.path.dirname(output_fpaths[0]), "cgviz_vs_jasen_heatmap.png")
        barplot_fpath = os.path.join(os.path.dirname(output_fpaths[0]), "null_alleles_barplot.png")
        null_alleles_count = self.get_null_allele_counts(input_files)
        self.plot_barplot(null_alleles_count, barplot_fpath)
        sample_ids = [os.path.basename(input_file).replace("_result.json", "") for input_file in input_files]
        cgviz_matrix_df = self.generate_matrix(sample_ids, self.get_cgviz_cgmlst_data)
        jasen_matrix_df = self.generate_matrix(sample_ids, self.get_jasen_cgmlst_data)
        distance_df = jasen_matrix_df - cgviz_matrix_df
        distance_df = distance_df.astype(float)
        distance_df.to_csv(output_csv_fpath, index=True, header=True)
        # self.plot_heatmap(distance_df, output_plot_fpath)
