"""
This script scrapes the manually downloaded HTML files to extract event data into InfluxDB.
"""

from datetime import datetime
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
from bs4 import BeautifulSoup
import json
import os
import pytz

from tools.config import INFLUXDB_URL, INFLUXDB_TOKEN, INFLUXDB_ORG, INFLUXDB_BUCKET

coords = [53.486389, -2.199722]
cutoff_date = datetime.strptime("2024-05-14", "%Y-%m-%d") # CoOpLive opening date

def convert_to_utc(local_date_str, local_time_str, timezone="Europe/London"):
    local_tz = pytz.timezone(timezone)
    local_datetime = datetime.strptime(f"{local_date_str} {local_time_str}", "%Y-%m-%d %H:%M")
    local_datetime = local_tz.localize(local_datetime)
    utc_datetime = local_datetime.astimezone(pytz.utc)
    return utc_datetime.isoformat()

def write_to_influxdb(data_points):
    try:
        with InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG) as client:
            write_api = client.write_api(write_options=SYNCHRONOUS)
            write_api.write(bucket=INFLUXDB_BUCKET, org=INFLUXDB_ORG, record=data_points)
    except Exception as e:
        print(f"Error writing to InfluxDB: {e}")

current_page = 1
while True:
    file_path = f"{current_page}.html"
    if not os.path.exists(file_path):
        print("No more files to process. Stopping.")
        break

    with open(file_path, "r", encoding="utf-8") as file:
        html = file.read()

    soup = BeautifulSoup(html, "html.parser")

    script = soup.find("script", type="application/ld+json")

    if script:
        structured_data = json.loads(script.string)

        # Extract events
        events = structured_data.get("event", [])
        currentDate = None
        data_points = []

        for event in events:
            if event.get('startDate') == currentDate:
                print("Duplicate event. Skipping.")
                continue  # Remove duplicates
            currentDate = event.get('startDate')
            event_date = datetime.strptime(event.get('startDate'), "%Y-%m-%d")

            if event_date < cutoff_date:
                print("Event date is before CoOpLive opening date. Skipping.")
                continue

            # assuming 7:30 PM local time
            utc_time = convert_to_utc(event.get('startDate'), "19:30")

            point = Point("Event") \
                .tag("venue", "CoOpLive") \
                .tag("event_type", "concert") \
                .tag("event_name", event.get("name")) \
                .tag("location", coords) \
                .field("estimated_attendance", 0) \
                .time(utc_time)

            data_points.append(point)

        write_to_influxdb(data_points)

    current_page += 1
