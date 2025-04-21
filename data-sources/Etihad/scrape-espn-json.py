"""
This script scrapes the manually downloaded HTML files to extract event data into InfluxDB.
"""

from datetime import datetime
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
import json
import os

from tools.config import INFLUXDB_URL, INFLUXDB_TOKEN, INFLUXDB_ORG, INFLUXDB_BUCKET

coords = [53.483056, -2.200278]
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
    events = json_data.get("page").get("content").get("results").get("events")

    for event in events:
        if not event.get("venue") :
            print("No venue specified. Skipping.")
            continue
        elif event.get("venue").get("fullName") != "Etihad Stadium":
            print("Match is not at location specified. Skipping.")
            continue

        event_date = event.get("date")
        teams = event.get("teams")

        point = Point("Event") \
            .tag("venue", "Etihad") \
            .tag("event_type", "match") \
            .tag("event_name", teams[1].get("shortDisplayName") + " @ " + teams[0].get("shortDisplayName")) \
            .tag("location", coords) \
            .field("estimated_attendance", 0) \
            .time(event_date)

        print(point.to_line_protocol())
        print(event_date)
        data_points.append(point)

    write_to_influxdb(data_points)
