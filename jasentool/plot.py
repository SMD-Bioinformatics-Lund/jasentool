"""Module for plotting graphs"""

import numpy as np
import matplotlib.pyplot as plt

class Plot:
    """Class for plotting graphs"""
    def plot_barplot(self, count_dict, output_plot_fpath, xlabel, ylabel, title, filter_thresh=1000):
        """Plot general barplot"""
        filtered_dict = {k: v for k, v in count_dict.items() if v >= filter_thresh}
        sorted_filtered_dict = dict(sorted(filtered_dict.items(), key=lambda item: item[1]))
        categories = list(sorted_filtered_dict.keys())
        counts = list(sorted_filtered_dict.values())

        plt.figure(figsize=(10, 8))
        bars = plt.bar(categories, counts, color="skyblue")

        plt.xlabel(xlabel)
        plt.ylabel(ylabel)
        plt.title(title)
        plt.xticks(rotation=90)
        for bar in bars:
            yval = bar.get_height()
            plt.text(bar.get_x() + bar.get_width()/2, yval + 1, yval, ha="center", va="bottom")

        plt.tight_layout()
        plt.savefig(output_plot_fpath, dpi=600)

    def plot_boxplot(self, count_dict, output_plot_fpath, xlabel, title, threshold=None):
        """Plot general boxplot"""
        counts = list(count_dict.values())
        plt.figure(figsize=(10, 8))
        plt.boxplot(counts, vert=True, patch_artist=True)
        plt.xlabel(xlabel)
        plt.title(title)

        min_value = np.min(counts)

        plt.annotate(f"Min: {min_value}", xy=(1, min_value), xytext=(1.05, min_value),
            arrowprops={"facecolor": 'red', "shrink": 0.05},
            horizontalalignment="left")

        if threshold:
            threshold_csv_output = "sample_name,count\n"
            for key, value in count_dict.items():
                if value > threshold:
                    threshold_csv_output += f"{key},{value}\n"
                    plt.annotate(f"{key} ({value})", xy=(1, value), xytext=(1.1, value),
                        arrowprops={"facecolor": 'red', "shrink": 0.05},
                        horizontalalignment="left", color="red")
            return threshold_csv_output
        plt.savefig(output_plot_fpath, dpi=600)
        return "sample_name,count\n"
