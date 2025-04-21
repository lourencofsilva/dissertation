"""
This script scrapes the manually downloaded HTML files to extract event data into InfluxDB.
"""

from datetime import datetime, timezone
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
from bs4 import BeautifulSoup
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

current_page = "24-25"
file_path = f"{current_page}.html"
if not os.path.exists(file_path):
    print("No more files to process. Stopping.")
    exit()

with open(file_path, "r", encoding="utf-8") as file:
    html = file.read()

soup = BeautifulSoup(html, "html.parser")

script = soup.find("script", type="application/ld+json")

if script:
    structured_data = json.loads(script.string)

    # Extract events
    events = structured_data
    data_points = []

    for event in events:
        if event.get("location").get("name") != "Etihad Stadium":
            print("Match is not at location specified. Skipping.")
            continue

        event_date = datetime.fromisoformat(event.get('startDate'))

        utc_time = event_date.astimezone(timezone.utc).isoformat()

        if event_date > cutoff_date.astimezone(timezone.utc):
            print("Event date is after data collection date. Skipping.")
            continue

        point = Point("Event") \
            .tag("venue", "Etihad") \
            .tag("event_type", "match") \
            .tag("event_name", event.get("name")) \
            .tag("location", coords) \
            .field("estimated_attendance", 0) \
            .time(utc_time)

        print(point.to_line_protocol())
        print(utc_time)
        data_points.append(point)

    write_to_influxdb(data_points)
