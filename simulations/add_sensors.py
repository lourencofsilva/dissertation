"""
This script queries InfluxDB for sensor data and places induction loop sensors on the SUMO network for a generated scenario.
"""

import ast
import math
import os
from influxdb_client import InfluxDBClient
import sumolib
import xml.etree.ElementTree as ET
from tools.config import INFLUXDB_URL, INFLUXDB_TOKEN, INFLUXDB_ORG, INFLUXDB_BUCKET

ROOT = "base-sim/"

NETWORK_FILE =  ROOT + "osm.net.xml.gz"
CONFIG_FILE =  ROOT + "osm.sumocfg"
OUTPUT_FILE = ROOT + "sensors.add.xml"

# Direction mappings for SUMO
direction_mapping = {
    "n": (90, 270),
    "ne": (45, 225),
    "e": (0, 180),
    "se": (315, 135),
    "s": (270, 90),
    "sw": (225, 45),
    "w": (180, 0),
    "nw": (135, 315),
}

def euclidean_distance(p1, p2):
    return math.sqrt((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2)

# Adapted from https://stackoverflow.com/a/6853926
def point_to_polyline_distance(point, polyline):
    min_dist = float('inf')
    best_pos = 0.0
    cumulative_length = 0.0
    for i in range(len(polyline) - 1):
        seg_start = polyline[i]
        seg_end = polyline[i + 1]
        seg_vec = (seg_end[0] - seg_start[0], seg_end[1] - seg_start[1])
        seg_len = euclidean_distance(seg_start, seg_end)
        if seg_len == 0:
            continue
        dx = point[0] - seg_start[0]
        dy = point[1] - seg_start[1]
        t = (dx * seg_vec[0] + dy * seg_vec[1]) / (seg_len ** 2)
        t = max(0, min(1, t))
        proj = (seg_start[0] + t * seg_vec[0], seg_start[1] + t * seg_vec[1])
        dist = euclidean_distance(point, proj)
        if dist < min_dist:
            min_dist = dist
            best_pos = cumulative_length + t * seg_len
        cumulative_length += seg_len
    return min_dist, best_pos

def get_lane_orientation(lane):
    shape = lane.getShape()
    if len(shape) < 2:
        return None
    x1, y1 = shape[0]
    x2, y2 = shape[-1]
    angle = math.degrees(math.atan2(y2 - y1, x2 - x1)) % 360
    return angle

def query_sensor_data():
    client = InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG)
    query_api = client.query_api()
    flux_query = f'''
    from(bucket: "{INFLUXDB_BUCKET}")
      |> range(start: -30d)
      |> filter(fn: (r) => r["_measurement"] == "Traffic")
      |> filter(fn: (r) => r["sensor_type"] == "vehicle-speed")
    '''
    tables = query_api.query(query=flux_query, org=INFLUXDB_ORG)
    sensors = {}
    for table in tables:
        for record in table.records:
            platform_id = record.values.get("platform_id")
            sensor_id = record.values.get("sensor_id")
            # Build a unique key: platform_id__sensor_id
            uid = platform_id + "__" + sensor_id
            if sensor_id is None or not sensor_id.startswith("avgspeed_") or uid in sensors:
                continue
            parts = sensor_id.split("_")
            if len(parts) < 2:
                continue
            direction = parts[1].lower()
            if direction not in direction_mapping:
                print(f"Sensor {uid} has unknown direction: {direction}")
                continue
            loc_str = record.values.get("location")
            try:
                loc = ast.literal_eval(loc_str)
                if isinstance(loc, (list, tuple)) and len(loc) == 2:
                    sensor_coord = (float(loc[0]), float(loc[1]))
                    sensors[uid] = {"coord": sensor_coord, "direction": direction}
            except Exception as e:
                print(f"Error parsing location for sensor {uid}: {loc_str} -> {e}")
    client.close()
    print(f"Queried {len(sensors)} sensor records from InfluxDB.")
    return sensors


def modify_additional_files(xml_file, new_files, output_file=None):
    tree = ET.parse(xml_file)
    root = tree.getroot()

    # Find the additional-files element
    additional_elem = root.find(".//input/additional-files")
    if additional_elem is not None:
        existing_files = additional_elem.get("value", "").split()
        updated_files = ",".join(set(existing_files + new_files))
        additional_elem.set("value", updated_files)

    # Save the modified XML
    if output_file is None:
        output_file = xml_file

    tree.write(output_file, encoding="UTF-8", xml_declaration=True)

    print(f"Updated additional-files value to '{updated_files}' in '{output_file}'")

def main():
    sensors = query_sensor_data()
    if not os.path.exists(NETWORK_FILE):
        print(f"Network file {NETWORK_FILE} not found!")
        return
    net = sumolib.net.readNet(NETWORK_FILE)
    minX, minY, maxX, maxY = net.getBoundary()
    print(f"Network boundary (SUMO coords): {minX}, {minY}, {maxX}, {maxY}")

    sensor_xml_entries = []
    for sensor_id, sensor_info in sensors.items():
        lon, lat = sensor_info["coord"]
        print(f"Sensor {sensor_id} original (lon, lat): ({lon}, {lat})")
        # Convert geographic coordinates to SUMO network coordinates.
        sensor_xy = net.convertLonLat2XY(lon, lat)
        print(f"Sensor {sensor_id} converted to SUMO coords: {sensor_xy}")
        if not (minX <= sensor_xy[0] <= maxX and minY <= sensor_xy[1] <= maxY):
            print(f"Sensor {sensor_id} at {sensor_xy} is outside network bounds; skipping.")
            continue

        sensor_dir = sensor_info["direction"]
        if sensor_dir not in direction_mapping:
            print(f"Sensor {sensor_id} has unknown direction '{sensor_dir}'; skipping.")
            continue
        primary_angle, _ = direction_mapping[sensor_dir]
        desired_angle = primary_angle

        sensor_found = False
        # Add a sensor for every lane that qualifies.
        for edge in net.getEdges():
            for lane in edge.getLanes():
                polyline = lane.getShape()
                dist, pos = point_to_polyline_distance(sensor_xy, polyline)
                # Only consider lanes within 20 meters.
                if dist > 20:
                    continue
                lane_angle = get_lane_orientation(lane)
                if lane_angle is None:
                    continue
                diff = abs(lane_angle - desired_angle)
                if diff > 180:
                    diff = 360 - diff
                if diff <= 45:
                    sensor_found = True
                    # Create a unique detector id for this lane, e.g. sensorID_laneID
                    detector_id = f"{sensor_id}_{lane.getID()}"
                    lane_id = lane.getID()
                    pos_str = f"{pos:.2f}"
                    xml_entry = (
                        f'<inductionLoop id="{detector_id}" lane="{lane_id}" pos="{pos_str}" '
                        f'period="300" file="{sensor_id}.out"/>'
                    )
                    sensor_xml_entries.append(xml_entry)
                    print(f"Placed sensor {detector_id} on lane {lane_id} at pos {pos_str} (dist {dist:.2f}).")
        if not sensor_found:
            print(f"Could not find any suitable lane for sensor {sensor_id} with direction '{sensor_dir}'.")

    # Write sensor definitions
    with open(OUTPUT_FILE, "w") as f:
        f.write("<additional>\n")
        for entry in sensor_xml_entries:
            f.write("    " + entry + "\n")
        f.write("</additional>\n")
    print(f"Wrote {len(sensor_xml_entries)} sensor definitions to {OUTPUT_FILE}")
    modify_additional_files(CONFIG_FILE, [OUTPUT_FILE.replace(ROOT, "")])

if __name__ == "__main__":
    main()
