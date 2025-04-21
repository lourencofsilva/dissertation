"""
This script generates demand files for SUMO simulations based on historical real-world sensor data.
"""

import os
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from influxdb_client import InfluxDBClient
import sumolib

from tools.config import INFLUXDB_URL, INFLUXDB_TOKEN, INFLUXDB_ORG, INFLUXDB_BUCKET

def iso_to_seconds(iso_str):
    t = datetime.fromisoformat(iso_str.replace("Z", ""))
    return (t - SIM_START).total_seconds()


def load_sensors_from_xml(xml_file):
    tree = ET.parse(xml_file)
    root = tree.getroot()
    sensor_groups = {}
    for elem in root.findall("inductionLoop"):
        uid = elem.attrib.get("id")
        lane = elem.attrib.get("lane")
        pos = float(elem.attrib.get("pos", "0"))
        file_attr = elem.attrib.get("file")
        if uid and lane and file_attr:
            group_key = file_attr.replace(".out", "")
            if group_key not in sensor_groups:
                sensor_groups[group_key] = []
            sensor_groups[group_key].append({"id": uid, "lane": lane, "pos": pos})
    total = sum(len(v) for v in sensor_groups.values())
    print(f"Loaded {total} sensors in {len(sensor_groups)} groups from {xml_file}")
    return sensor_groups


def query_sensor_count_data(sim_date):
    client = InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG)
    query_api = client.query_api()
    start_time = f"{sim_date}T00:00:00Z"
    stop_time = f"{sim_date}T23:59:59Z"
    flux_query = f'''
    from(bucket: "{INFLUXDB_BUCKET}")
      |> range(start: {start_time}, stop: {stop_time})
      |> filter(fn: (r) => r["_measurement"] == "Traffic")
      |> filter(fn: (r) => r["sensor_type"] == "vehicle-count")
      |> aggregateWindow(every: 5m, fn: mean, createEmpty: false)
      |> duplicate(column: "_stop", as: "time")
    '''
    tables = query_api.query(query=flux_query, org=INFLUXDB_ORG)
    count_data = {}
    for table in tables:
        for record in table.records:
            uid = record.values.get("platform_id") + "__" + record.values.get("sensor_id")
            count_value = record.get_value()
            window_end_iso = record.get_time().isoformat()
            window_end = iso_to_seconds(window_end_iso)
            window_begin = window_end - TIME_WINDOW.total_seconds()
            if uid not in count_data:
                count_data[uid] = []
            count_data[uid].append((window_begin, window_end, count_value))
    client.close()
    for uid in count_data:
        count_data[uid].sort(key=lambda x: x[0])
    print(f"Queried count data for {len(count_data)} sensor groups from InfluxDB.")
    return count_data


def query_sensor_speed_data(sim_date):
    client = InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG)
    query_api = client.query_api()
    start_time = f"{sim_date}T00:00:00Z"
    stop_time = f"{sim_date}T23:59:59Z"
    flux_query = f'''
    from(bucket: "{INFLUXDB_BUCKET}")
      |> range(start: {start_time}, stop: {stop_time})
      |> filter(fn: (r) => r["_measurement"] == "Traffic")
      |> filter(fn: (r) => r["sensor_type"] == "vehicle-speed")
      |> aggregateWindow(every: 5m, fn: mean, createEmpty: false)
      |> duplicate(column: "_stop", as: "time")
    '''
    tables = query_api.query(query=flux_query, org=INFLUXDB_ORG)
    speed_data = {}
    for table in tables:
        for record in table.records:
            uid = record.values.get("platform_id") + "__" + record.values.get("sensor_id")
            speed_kmh = record.get_value()
            speed_ms = speed_kmh / 3.6 if speed_kmh is not None else None
            window_end_iso = record.get_time().isoformat()
            window_end = iso_to_seconds(window_end_iso)
            window_begin = window_end - TIME_WINDOW.total_seconds()
            if uid not in speed_data:
                speed_data[uid] = []
            speed_data[uid].append((window_begin, window_end, speed_ms))
    client.close()
    for uid in speed_data:
        speed_data[uid].sort(key=lambda x: x[0])
    print(f"Queried speed data for {len(speed_data)} sensor groups from InfluxDB.")
    return speed_data


def generate_data_file(sensor_groups, count_data, speed_data, net):
    data_elem = ET.Element("data")
    # Use max sensor group number of windows
    sample_key = max(count_data.keys(), key=lambda x: len(count_data[x]))
    num_windows = len(count_data[sample_key])
    print(f"Generating data for {num_windows} time intervals (5 minutes each).")

    for i in range(num_windows):
        win_begin, win_end, _ = count_data[sample_key][i]
        interval_elem = ET.SubElement(data_elem, "interval",
                                      id=f"interval_{i}",
                                      begin=f"{win_begin:.1f}",
                                      end=f"{win_end:.1f}")
        for group_key, sensor_list in sensor_groups.items():
            count_key = group_key.replace("avgspeed", "car") # Replace speed with count
            if count_key not in count_data or group_key not in speed_data:
                continue
            try:
                _, _, count_value = count_data[count_key][i]
                _, _, speed_value = speed_data[group_key][i]
            except IndexError:
                continue
            # Use the first sensor in the group to get the associated edge id.
            sensor = sensor_list[0]
            lane_id = sensor["lane"]
            try:
                lane_obj = net.getLane(lane_id)
                edge_id = lane_obj.getEdge().getID()
            except Exception as e:
                print(f"Could not get edge for lane {lane_id} in sensor group {group_key}: {e}")
                continue
            # Create the <edge> element for this interval.
            ET.SubElement(interval_elem, "edge",
                                      id=edge_id,
                                      entered=f"{count_value * SCALING_FACTOR:.0f}",
                                      speed=f"{speed_value:.2f}")
    return ET.ElementTree(data_elem)


def main():
    # Genenerate random routes
    os.system(f"python3 $SUMO_HOME/tools/randomTrips.py -n {NETWORK_FILE} -r {ROUTES_FILE} --period 1 --end 86400")

    # Query historical sensor count and speed data.
    count_data = query_sensor_count_data(SIMULATION_DATE)
    speed_data = query_sensor_speed_data(SIMULATION_DATE)

    # Load sensor placements from sensors.add.xml.
    sensor_groups = load_sensors_from_xml(SENSORS_XML_FILE)

    # Load the SUMO network.
    if not os.path.exists(NETWORK_FILE):
        print(f"Network file {NETWORK_FILE} not found!")
        return
    net = sumolib.net.readNet(NETWORK_FILE)
    minX, minY, maxX, maxY = net.getBoundary()
    print(f"Network boundary (SUMO coords): {minX}, {minY}, {maxX}, {maxY}")

    # Generate the data file.
    tree = generate_data_file(sensor_groups, count_data, speed_data, net)
    tree.write(OUTPUT_DATA_FILE, encoding="utf-8", xml_declaration=True)
    print(f"Wrote data file to {OUTPUT_DATA_FILE}")

    # Run routeSampler.py to generate demand files
    os.system(f"python3 $SUMO_HOME/tools/routeSampler.py -r {ROUTES_FILE} --edgedata-files {OUTPUT_DATA_FILE} -o {OUTPUT_FILE}")


if __name__ == "__main__":
    dates = [
        "example-date",
    ]

    for SIMULATION_DATE in dates:
        ROOT = f"example-root/{SIMULATION_DATE}/"

        NETWORK_FILE = ROOT + "osm.net.xml.gz"
        SENSORS_XML_FILE = ROOT + "sensors.add.xml"
        OUTPUT_DATA_FILE = ROOT + "demand_data.xml"
        OUTPUT_FILE = ROOT + "demand.xml"
        ROUTES_FILE = ROOT + "routes.rou.xml"

        SIM_START = datetime.fromisoformat(SIMULATION_DATE + "T00:00:00Z")
        TIME_WINDOW = timedelta(minutes=5)
        SCALING_FACTOR = 0.7  # Scale simulation to prevent total network congestion (due to simulation inefficiencies)

        main()
