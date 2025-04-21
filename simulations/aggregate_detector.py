"""
This script aggregates the detector data from the XML detector files of the simulation.

After running a simulation, this allows to aggregate and plot the vehicle count and mean speed over time for sensor locations.
"""

import sys
import xml.etree.ElementTree as ET
import matplotlib.pyplot as plt
import numpy as np

MPS_TO_MPH = 2.23694

def extract_edge_id(interval_id):
    """
    Given an interval id like:
      drakewell__1163__avgspeed_nw_949385199-AddedOffRampEdge_0
    extract the common edge id.
    For example, return "949385199-AddedOffRampEdge".
    """
    parts = interval_id.split("_")
    if len(parts) < 2:
        return interval_id
    return parts[-2]


def aggregate_detector_data(input_file):
    """
    Aggregates the detector data from the XML detector files of the simulation.
    """
    tree = ET.parse(input_file)
    root = tree.getroot()  # expect <detector> as root

    time_groups = {}
    for interval in root.findall("interval"):
        try:
            begin = float(interval.attrib.get("begin", "0"))
            end = float(interval.attrib.get("end", "0"))
        except ValueError:
            continue
        key = (begin, end)
        if key not in time_groups:
            time_groups[key] = []
        time_groups[key].append(interval)

    aggregated = []
    sample_interval = next(iter(root.findall("interval")), None)
    if sample_interval is not None:
        sample_id = sample_interval.attrib.get("id", "")
        common_edge = extract_edge_id(sample_id)
    else:
        common_edge = "unknown"

    # Process each time window
    for (begin, end) in sorted(time_groups.keys()):
        intervals = time_groups[(begin, end)]
        total_count = 0
        speeds = []
        for elem in intervals:
            try:
                count = int(elem.attrib.get("nVehEntered", "0"))
            except ValueError:
                count = 0
            total_count += count
            try:
                speed = float(elem.attrib.get("speed", "-1"))
            except ValueError:
                speed = -1
            # Consider only valid speeds (>= 0)
            if speed >= 0:
                speeds.append(speed)
        if speeds:
            mean_speed = sum(speeds) / len(speeds)
        else:
            mean_speed = -1
        # Convert mean speed from m/s to mph
        if mean_speed >= 0:
            mean_speed *= MPS_TO_MPH
        aggregated.append((begin, end, total_count, mean_speed))
    return aggregated, common_edge


def write_aggregated_data_xml(aggregated, edge_id, output_file):
    data_elem = ET.Element("data")
    for i, (begin, end, total_count, mean_speed) in enumerate(aggregated):
        interval_elem = ET.SubElement(data_elem, "interval",
                                      id=f"interval_{i}",
                                      begin=f"{begin:.1f}",
                                      end=f"{end:.1f}")
        ET.SubElement(interval_elem, "edge",
                      id=edge_id,
                      entered=str(total_count),
                      speed=f"{mean_speed:.2f}")
    tree = ET.ElementTree(data_elem)
    tree.write(output_file, encoding="utf-8", xml_declaration=True)
    print(f"Wrote aggregated data to {output_file}")


def remove_outliers(data, column_index):
    values = [row[column_index] for row in data if row[column_index] >= 0]
    if not values:
        return data
    q1 = np.percentile(values, 25)
    q3 = np.percentile(values, 75)
    iqr = q3 - q1
    lower_bound = q1 - 1.5 * iqr
    upper_bound = q3 + 1.5 * iqr

    return [row for row in data if lower_bound <= row[column_index] <= upper_bound]


def plot_aggregated_data(aggregated):
    """
    Plots the aggregated vehicle count and mean speed over time after removing outliers.
    """
    # Remove outliers separately for counts and speeds
    filtered_counts = remove_outliers(aggregated, column_index=2)
    filtered_speeds = remove_outliers(aggregated, column_index=3)

    # Extract times and values for filtered data (times converted to minutes)
    times_counts = [(begin + end) / 120.0 for (begin, end, _, _) in filtered_counts]
    counts = [total_count for (_, _, total_count, _) in filtered_counts]

    times_speeds = [(begin + end) / 120.0 for (begin, end, _, _) in filtered_speeds]
    speeds = [mean_speed for (_, _, _, mean_speed) in filtered_speeds]

    fig, ax1 = plt.subplots(figsize=(10, 5))

    color = 'tab:blue'
    ax1.set_xlabel("Time (minutes)")
    ax1.set_ylabel("Count (nVehEntered)", color=color)
    ax1.plot(times_counts, counts, marker='o', linestyle='-', color=color, label="Filtered Count")
    ax1.tick_params(axis='y', labelcolor=color)

    ax2 = ax1.twinx()  # Second y-axis for speed
    color = 'tab:red'
    ax2.set_ylabel("Mean Speed (mph)", color=color)
    ax2.plot(times_speeds, speeds, marker='x', linestyle='--', color=color, label="Filtered Speed")
    ax2.tick_params(axis='y', labelcolor=color)

    fig.tight_layout()
    plt.title("Aggregated Sensor Data Over Time (Outliers Removed)")
    plt.show()


def aggregate_demand_data(demand_file):
    tree = ET.parse(demand_file)
    root = tree.getroot()  # expected <data> as root

    aggregated = []
    for interval in root.findall("interval"):
        try:
            begin = float(interval.attrib.get("begin", "0"))
            end = float(interval.attrib.get("end", "0"))
        except ValueError:
            continue
        speeds = []
        for edge in interval.findall("edge"):
            try:
                speed = float(edge.attrib.get("speed", "-1"))
                if speed >= 0:
                    speeds.append(speed)
            except ValueError:
                continue
        if speeds:
            mean_speed = sum(speeds) / len(speeds)
        else:
            mean_speed = -1
        if mean_speed >= 0:
            mean_speed *= MPS_TO_MPH
        aggregated.append((begin, end, mean_speed))
    return aggregated


def plot_speed_comparison(sim_data, demand_data):
    """
    Plots the comparison of real vs sim data
    """
    # Sort the data by time if not already sorted
    sim_data_sorted = sorted(sim_data, key=lambda x: x[0])
    demand_data_sorted = sorted(demand_data, key=lambda x: x[0])

    times_sim = [(begin + end) / 120.0 for (begin, end, _, _) in sim_data_sorted]
    speeds_sim = [mean_speed for (_, _, _, mean_speed) in sim_data_sorted]

    times_demand = [(begin + end) / 120.0 for (begin, end, mean_speed) in demand_data_sorted]
    speeds_demand = [mean_speed for (_, _, mean_speed) in demand_data_sorted]

    plt.figure(figsize=(10, 5))
    plt.plot(times_demand, speeds_demand, marker='o', linestyle='-', label='Actual Speed')
    plt.plot(times_sim, speeds_sim, marker='x', linestyle='--', label='Simulated Speed')
    plt.xlabel("Time (minutes)")
    plt.ylabel("Mean Speed (mph)")
    plt.title("Simulated vs Actual Mean Speed Over Time")
    plt.legend()
    plt.show()


def main():
    if len(sys.argv) < 4:
        print("Usage: {} <input_sensor_file.xml> <output_aggregated_data.xml> <demand_data.xml>".format(sys.argv[0]))
        sys.exit(1)
    input_sensor_file = sys.argv[1]
    output_file = sys.argv[2]
    demand_file = sys.argv[3]

    # Process simulation detector file
    sim_aggregated, edge_id = aggregate_detector_data(input_sensor_file)
    write_aggregated_data_xml(sim_aggregated, edge_id, output_file)
    plot_aggregated_data(sim_aggregated)

    # Process demand (actual) data file
    demand_aggregated = aggregate_demand_data(demand_file)

    # Filtering
    valid_sim = []
    valid_demand = []
    n = min(len(sim_aggregated), len(demand_aggregated))
    for i in range(n):
        if demand_aggregated[i][2] > 0:
            valid_sim.append(sim_aggregated[i])
            valid_demand.append(demand_aggregated[i])

    if not valid_demand:
        print("No valid demand intervals with non-zero speed found. Exiting.")
        sys.exit(1)

    plot_speed_comparison(valid_sim, valid_demand)

    # Compute error metrics
    errors = []
    demand_speeds = []
    for sim, demand in zip(valid_sim, valid_demand):
        sim_speed = sim[3]
        demand_speed = demand[2]
        errors.append(sim_speed - demand_speed)
        demand_speeds.append(demand_speed)

    errors = np.array(errors)
    demand_speeds = np.array(demand_speeds)

    mae = np.mean(np.abs(errors))
    mse = np.mean(errors ** 2)
    mape = np.mean(np.abs(errors / demand_speeds)) * 100

    print(f"MAE: {mae:.3f} mph")
    print(f"MSE: {mse:.3f} (mph)^2")
    print(f"MAPE: {mape:.3f}%")

if __name__ == "__main__":
    main()
