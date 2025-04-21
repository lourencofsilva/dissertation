import os
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from tabulate import tabulate

sim_root = "example-root"
modes_to_remove = ["lower_limit", "predictive_30"]

all_dfs = []
modes_per_sim = []

for subdir in os.listdir(sim_root):
    full_path = os.path.join(sim_root, subdir)
    if os.path.isdir(full_path):
        csv_path = os.path.join(full_path, "aggregated_metrics.csv")
        if os.path.exists(csv_path):
            print(f"Processing directory: {subdir}")
            df = pd.read_csv(csv_path)
            # Remove rows with control_mode in modes_to_remove
            df = df[~df["control_mode"].isin(modes_to_remove)]
            all_dfs.append(df)
            # Store the set of control modes for this simulation run
            modes_per_sim.append(set(df["control_mode"].unique()))

if all_dfs:
    # Compute the intersection of control modes present in every simulation run
    common_modes = set.intersection(*modes_per_sim)
    print("Common control modes across all simulations:", common_modes)

    if not common_modes:
        print("No common control modes found in every simulation run. Exiting.")
    else:
        combined_df = pd.concat(all_dfs, ignore_index=True)
        # Filter combined_df to only include rows with control modes present in every simulation
        combined_df = combined_df[combined_df["control_mode"].isin(common_modes)]

        metrics = ["avg_duration", "avg_emission", "avg_speed", "avg_timeLoss"]

        agg_metrics = combined_df.groupby("control_mode")[metrics].agg(
            ["mean", "std", "min", "max", "median"]).reset_index()

        # Flatten multi-index columns
        agg_metrics.columns = ['_'.join(col).strip() if col[1] != "" else col[0] for col in agg_metrics.columns.values]

        # Get baseline row (for control_mode == "baseline")
        baseline = agg_metrics.loc[agg_metrics["control_mode"] == "baseline"]
        if not baseline.empty:
            baseline_row = baseline.iloc[0]
            # Compute percentage change for each metric (using mean values)
            for metric in metrics:
                agg_metrics[f"perc_change_{metric}"] = (
                    (agg_metrics[f"{metric}_mean"] - baseline_row[f"{metric}_mean"]) /
                    baseline_row[f"{metric}_mean"]
                ) * 100

            agg_metrics.to_csv("combined_aggregated_metrics.csv", index=False)
            print("Saved combined aggregated metrics with percentage changes to combined_aggregated_metrics.csv")

            # Plot percentage changes for each metric relative to baseline
            metrics_to_plot = {
                "perc_change_avg_emission": "Emission (% Change)",
                "perc_change_avg_duration": "Trip Duration (% Change)",
                "perc_change_avg_timeLoss": "TimeLoss (% Change)"
            }
            sns.set(style="whitegrid")
            for metric, ylabel in metrics_to_plot.items():
                plt.figure(figsize=(10, 6))
                sns.barplot(data=agg_metrics, x="control_mode", y=metric)
                plt.xticks(rotation=45)
                plt.xlabel("Control Mode")
                plt.ylabel(ylabel)
                plt.title(f"{ylabel} Relative to Baseline - 2024 Simulations")
                plt.tight_layout()
                plt.savefig(f"{metric}_perc_change.png")
                plt.show()

            # Combined plot for all percentage changes
            perc_cols = ["perc_change_avg_emission", "perc_change_avg_duration", "perc_change_avg_timeLoss"]
            metrics_long = agg_metrics.melt(id_vars=["control_mode"],
                                            value_vars=perc_cols,
                                            var_name="Metric",
                                            value_name="Percentage Change")

            metrics_long["Metric"] = metrics_long["Metric"].map(metrics_to_plot)

            plt.figure(figsize=(10, 6))
            sns.barplot(data=metrics_long, x="control_mode", y="Percentage Change", hue="Metric")
            plt.xticks(rotation=45)
            plt.xlabel("Control Mode")
            plt.ylabel("Percentage Change (%)")
            plt.title("Simulation Results Relative to Baseline (Combined) - 2024 Simulations")
            plt.tight_layout()
            plt.savefig("combined_perc_change.png")
            plt.show()

            print("Descriptive Aggregated Metrics by Control Mode:")
            print(tabulate(agg_metrics, headers="keys", tablefmt="pipe", floatfmt=".2f"))
        else:
            print("No baseline data found!")
else:
    print("No aggregated_metrics.csv files found in any simulation directory.")
