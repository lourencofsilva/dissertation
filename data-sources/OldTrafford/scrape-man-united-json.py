"""
This script scrapes the manually downloaded HTML files to extract event data into InfluxDB.
"""

from datetime import datetime
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
import json
import os

from tools.config import INFLUXDB_URL, INFLUXDB_TOKEN, INFLUXDB_ORG, INFLUXDB_BUCKET

coords = [53.463056, -2.291389]
cutoff_date = datetime.strptime("2025-01-27", "%Y-%m-%d") # Data Collection Date

def write_to_influxdb(data_points):
    try:
        with InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG) as client:
            write_api = client.write_api(write_options=SYNCHRONOUS)
            write_api.write(bucket=INFLUXDB_BUCKET, org=INFLUXDB_ORG, record=data_points)
    except Exception as e:
        print(f"Error writing to InfluxDB: {e}")

files = os.listdir()

for file in files:
    if not file.endswith(".json"):
        continue

    with open(file, "r", encoding="utf-8") as file_data:
        json_data = json.load(file_data)

    # Extract events
    data_points = []
    events = json_data.get("ResultListResponse").get("response").get("docs")

    for event in events:
        if event.get("venuename_t") != "Old Trafford":
            print("Match is not at location specified. Skipping.")
            continue

        event_date = event.get("matchdate_tdt")

        point = Point("Event") \
            .tag("venue", "OldTrafford") \
            .tag("event_type", "match") \
            .tag("event_name", event.get("awayteamshortname_t") + " @ " + event.get("hometeamshortname_t")) \
            .tag("location", coords) \
            .field("estimated_attendance", 0) \
            .time(event_date)

        data_points.append(point)

    write_to_influxdb(data_points)
