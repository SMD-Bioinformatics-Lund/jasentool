"""Module for validating pipelines"""

import os
import json
from jasentool.database import Database
from jasentool.utils import Utils
from jasentool.matrix import Matrix
from jasentool.plot import Plot

class Validate:
    """Class to validate old pipeline (cgviz) with new pipeline (jasen)"""
    def __init__(self, input_dir, db_collection):
        self.input_dir = input_dir
        self.db_collection = db_collection

    def get_sample_name(self, results):
        """Get sample ID from input json"""
        return results["sample_name"]

    def get_species_name(self, results):
        """Get species name from input json"""
        return results["species_prediction"][0]["result"][0]["scientific_name"]

    def _check_exists(self, sample_name):
        """Check if sample name exists in mongodb"""
        return bool(list(Database.find(self.db_collection, {"id": sample_name}, {})))

    def search(self, search_query, search_kw, search_list):
        """Search for query in list of arrays"""
        return [element for element in search_list if element[search_kw] == search_query]

    def get_virulence_results(self, results):
        """Get virulence results"""
        return self.search("VIRULENCE", "type", results["element_type_result"])

    def get_pvl(self, results):
        """Get pvl result"""
        virulence_results = self.get_virulence_results(results)
        return bool(self.search("lukS-PV", "gene_symbol", virulence_results[0]["result"]["genes"]))

    def get_mlst(self, results):
        """Get mlst result"""
        return self.search("mlst", "type", results["typing_result"])

    def get_cgmlst(self, results):
        """Get cgmlst result"""
        return self.search("cgmlst", "type", results["typing_result"])

    def get_null_allele_counts(self, input_files):
        """Get null position counts"""
        null_alleles_count = {}
        sample_null_count = {}
        n_missing_loci = {}
        for input_file in input_files:
            sample_id = os.path.basename(input_file).replace("_result.json", "")
            sample_null_count[sample_id] = 0
            with open(input_file, 'r', encoding="utf-8") as fin:
                sample_json = json.load(fin)
                jasen_cgmlst = self.search("cgmlst", "type", sample_json["typing_result"])
                n_missing = int(jasen_cgmlst[0]["result"]["n_missing"])
                n_missing_loci[sample_id] = n_missing
                jasen_cgmlst_alleles = dict(jasen_cgmlst[0]["result"]["alleles"])
                for allele in jasen_cgmlst_alleles:
                    if type(jasen_cgmlst_alleles[allele]) == str:
                        sample_null_count[sample_id] += 1
                        if allele in null_alleles_count:
                            null_alleles_count[allele] += 1
                        else:
                            null_alleles_count[allele] = 1
        print(f"The average number of missing alleles per sample is {sum(sample_null_count.values()) / len(sample_null_count.values())}")
        return null_alleles_count, sample_null_count, n_missing_loci

    def get_mdb_cgv_data(self, sample_name):
        """Get sample mongodb data"""
        mdb_pvl = list(Database.get_pvl(self.db_collection, {"id": sample_name, "metadata.QC": "OK"}))
        mdb_mlst = list(Database.get_mlst(self.db_collection, {"id": sample_name, "metadata.QC": "OK"}))
        mdb_cgmlst = list(Database.get_cgmlst(self.db_collection, {"id": sample_name, "metadata.QC": "OK"}))
        try:
            mdb_pvl_present = int(mdb_pvl[0]["aribavir"]["lukS_PV"]["present"])
            mdb_mlst_seqtype = str(mdb_mlst[0]["mlst"]["sequence_type"]) if mdb_mlst[0]["mlst"]["sequence_type"] != "-" else str(None)
            mdb_mlst_alleles = mdb_mlst[0]["mlst"]["alleles"]
            mdb_cgmlst_alleles = mdb_cgmlst[0]["alleles"]
            return {"pvl": mdb_pvl_present, "mlst_seqtype": mdb_mlst_seqtype,
                    "mlst_alleles": mdb_mlst_alleles, "cgmlst_alleles": mdb_cgmlst_alleles}
        except IndexError:
            return False

    def get_fin_data(self, sample_json):
        """Get sample input file data"""
        fin_pvl_present = self.get_pvl(sample_json)
        fin_mlst = self.get_mlst(sample_json)
        fin_cgmlst = self.get_cgmlst(sample_json)
        fin_mlst_seqtype = str(fin_mlst[0]["result"]["sequence_type"])
        fin_mlst_alleles = fin_mlst[0]["result"]["alleles"]
        fin_cgmlst_alleles = list(fin_cgmlst[0]["result"]["alleles"].values())
        return {"pvl": fin_pvl_present, "mlst_seqtype": fin_mlst_seqtype,
                "mlst_alleles": fin_mlst_alleles, "cgmlst_alleles": fin_cgmlst_alleles}

    def compare_mlst_alleles(self, old_mlst_alleles, new_mlst_alleles):
        """Parse through mlst alleles of old and new pipeline and compare results"""
        match_count, total_count = 0, 0
        for allele in old_mlst_alleles:
            if str(old_mlst_alleles[allele]) == str(new_mlst_alleles[allele]):
                match_count += 1
            total_count += 1
        return 100*(match_count/total_count)

    def compare_cgmlst_alleles(self, old_cgmlst_alleles, new_cgmlst_alleles):
        """Parse through cgmlst alleles of old and new pipeline and compare results"""
        match_count, total_count = 0, 0
        for idx, old_allele in enumerate(old_cgmlst_alleles):
            if str(old_allele) == str(new_cgmlst_alleles[idx]):
                match_count += 1
            total_count += 1
        return 100*(match_count/total_count)

    def compare_data(self, sample_name, old_data, new_data):
        """Compare data between old pipeline and new pipeline"""
        pvl_comp = int(old_data["pvl"] == new_data["pvl"])
        mlst_seqtype_comp = int(old_data["mlst_seqtype"] == new_data["mlst_seqtype"])
        if mlst_seqtype_comp == 0:
            mlst_at_list = [f'{old_data["mlst_alleles"][gene]},{new_data["mlst_alleles"][gene]}'
                            for gene in sorted(old_data["mlst_alleles"].keys())]
            mlst_at_str = ",".join(mlst_at_list)
            return False, f'{sample_name},{old_data["mlst_seqtype"]},{new_data["mlst_seqtype"]},{mlst_at_str}'
        mlst_alleles = self.compare_mlst_alleles(old_data["mlst_alleles"], new_data["mlst_alleles"])
        cgmlst_alleles = self.compare_cgmlst_alleles(old_data["cgmlst_alleles"], new_data["cgmlst_alleles"])
        return True, f"{sample_name},{pvl_comp},{mlst_seqtype_comp},{mlst_alleles},{cgmlst_alleles}"

    def run(self, input_files, output_fpaths, combined_output, generate_matrix):
        """Execute validation of new pipeline (jasen)"""
        utils = Utils()
        # Plots
        plot = Plot()
        barplot_fpath = os.path.join(os.path.dirname(output_fpaths[0]), "null_alleles_barplot.png")
        sample_null_boxplot_fpath = os.path.join(os.path.dirname(output_fpaths[0]), "sample_null_boxplot.png")
        n_missing_boxplot_fpath = os.path.join(os.path.dirname(output_fpaths[0]), "n_missing_loci_boxplot.png")
        n_missing_csv_fpath = os.path.join(os.path.dirname(output_fpaths[0]), "n_missing_loci_above_threshold.csv")
        null_alleles_count, sample_null_count, n_missing_loci = self.get_null_allele_counts(input_files)
        _ = plot.plot_boxplot(sample_null_count, sample_null_boxplot_fpath, "Null allele count", "Number of null alleles per sample")
        threshold_csv_output = plot.plot_boxplot(n_missing_loci, n_missing_boxplot_fpath, "No. missing loci", "Number missing loci per sample", 100)
        plot.plot_barplot(null_alleles_count, barplot_fpath, "Alleles", "Count", "Null Allele Count Bar Plot")
        utils.write_out_txt(threshold_csv_output, n_missing_csv_fpath)
        if generate_matrix:
            matrix = Matrix(self.input_dir, self.db_collection)
            matrix.run(input_files, output_fpaths)
        # csv file headers
        csv_output = "sample_name,pvl,mlst_seqtype,mlst_allele_matches(%),cgmlst_allele_matches(%)"
        mlst_at_header = "old_arcC,new_arcC,old_aroE,new_aroE,old_glpF,new_glpF,old_gmk,new_gmk,old_pta,new_pta,old_tpi,new_tpi,old_yqiL,new_yqiL"
        failed_csv_output = f"sample_name,old_mlst_seqtype,new_mlst_seqtype,{mlst_at_header}"
        for input_idx, input_file in enumerate(input_files):
            with open(input_file, 'r', encoding="utf-8") as fin:
                sample_json = json.load(fin)
                sample_name = self.get_sample_name(sample_json)
                if not self._check_exists(sample_name):
                    print(f"The sample provided ({sample_name}) does not exist in the provided database ({Database.db_name}) or collection ({self.db_collection}).")
                    continue
                mdb_data_dict = self.get_mdb_cgv_data(sample_name)
                if mdb_data_dict:
                    fin_data_dict = self.get_fin_data(sample_json)
                    passed_val, compared_data_output = self.compare_data(sample_name, mdb_data_dict, fin_data_dict)
                    species_name = self.get_species_name(sample_json)
                    if species_name != "Staphylococcus aureus":
                        print(f"WARN: This sample is not saureus: {sample_name} (species prediction: {species_name})")
                    if passed_val:
                        csv_output += "\n" + compared_data_output
                    else:
                        failed_csv_output += "\n" + compared_data_output
            if not combined_output:
                utils.write_out_txt(csv_output, f"{output_fpaths[input_idx]}.csv")
                utils.write_out_txt(failed_csv_output, f"{output_fpaths[input_idx]}_failed.csv")
                csv_output = "pvl,mlst_seqtype,mlst_allele_matches(%),cgmlst_allele_matches(%)"
                failed_csv_output = "pvl,mlst_seqtype,mlst_allele_matches(%),cgmlst_allele_matches(%)"

        if combined_output:
            utils.write_out_txt(csv_output, f"{output_fpaths[0]}.csv")
            utils.write_out_txt(failed_csv_output, f"{output_fpaths[0]}_failed.csv")
