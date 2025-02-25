"""Module for plotting graphs"""

import numpy as np
import matplotlib.pyplot as plt

class Plot:
    """Class for plotting graphs"""
    def plot_barplot(self, count_dict, output_plot_fpath, xlabel, ylabel, title, filter_thresh=1000):
        filtered_dict = {k: v for k, v in count_dict.items() if v >= filter_thresh}
        sorted_filtered_dict = dict(sorted(filtered_dict.items(), key=lambda item: item[1]))
        categories = list(sorted_filtered_dict.keys())
        counts = list(sorted_filtered_dict.values())

        # print(f"The number of alleles that aren't null for more than 1000 samples is {len(categories)}")

        plt.figure(figsize=(10, 8))
        bars = plt.bar(categories, counts, color="skyblue")

        # Add titles and labels
        plt.xlabel(xlabel)
        plt.ylabel(ylabel)
        plt.title(title)

        # Rotate the x-axis labels by 90 degrees
        plt.xticks(rotation=90)

        # Add value labels on top of the bars
        for bar in bars:
            yval = bar.get_height()
            plt.text(bar.get_x() + bar.get_width()/2, yval + 1, yval, ha="center", va="bottom")

        plt.tight_layout()
        plt.savefig(output_plot_fpath, dpi=600)

    def plot_boxplot(self, count_dict, output_plot_fpath, xlabel, title, threshold=None):
        counts = list(count_dict.values())
        plt.figure(figsize=(10, 8))  # Optional: set the figure size
        plt.boxplot(counts, vert=True, patch_artist=True)  # `vert=True` for vertical boxplot, `patch_artist=True` for filled boxes

        # Add title and labels
        plt.xlabel(xlabel)
        plt.title(title)

        min_value = np.min(counts)

        # Label the minimum value on the plot
        plt.annotate(f"Min: {min_value}", xy=(1, min_value), xytext=(1.05, min_value),
            arrowprops=dict(facecolor="black", shrink=0.05),
            horizontalalignment="left")
        
        # Annotate values above the threshold
        if threshold:
            threshold_csv_output = "sample_name,count\n"
            for key, value in count_dict.items():
                if value > threshold:
                    threshold_csv_output += f"{key},{value}\n"
                    f"{key} ({value})"
                    plt.annotate(f"{key} ({value})", xy=(1, value), xytext=(1.1, value),
                        arrowprops=dict(facecolor="red", shrink=0.05),
                        horizontalalignment="left", color="red")
            return threshold_csv_output
        plt.savefig(output_plot_fpath, dpi=600)
        return "sample_name,count\n"
