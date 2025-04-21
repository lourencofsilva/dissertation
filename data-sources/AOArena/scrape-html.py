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

coords = [53.488056, -2.243889]

def convert_to_utc(local_date_str, local_time_str, timezone="Europe/London"):
    local_tz = pytz.timezone(timezone)
    local_datetime = datetime.strptime(f"{local_date_str} {local_time_str}", "%Y-%m-%d %H:%M")
    local_datetime = local_tz.localize(local_datetime)
    utc_datetime = local_datetime.astimezone(pytz.utc)
    return utc_datetime.isoformat()

def format_date_to_string(date_str):
    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
    return date_obj.strftime("%b %d, %Y")

def write_to_influxdb(data_points):
    try:
        with InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG) as client:
            write_api = client.write_api(write_options=SYNCHRONOUS)
            write_api.write(bucket=INFLUXDB_BUCKET, org=INFLUXDB_ORG, record=data_points)
    except Exception as e:
        print(f"Error writing to InfluxDB: {e}")

def is_concert_cancelled(event_date, soup):
    # Find all rows with strike-through dates and "Cancelled" labels
    cancelled_rows = soup.find_all("td", class_="table-cell-no-stretch")
    for row in cancelled_rows:
        date_span = row.find("span", class_="strike-through")
        if date_span and event_date in date_span.text:
            label = row.find("span", class_="label label-danger", title="Concert Cancelled")
            if label and "Cancelled" in label.text:
                return True
    return False

# Loop through HTML files in the current directory
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
            event_date = event.get('startDate')

            # Check if cancelled
            if is_concert_cancelled(format_date_to_string(event_date), soup):
                print(f"Concert on {event_date} is cancelled. Skipping.")
                continue  # Skip cancelled concerts

            # assuming 7:30 PM local time
            utc_time = convert_to_utc(event.get('startDate'), "19:30")

            point = Point("Event") \
                .tag("venue", "AOArena") \
                .tag("event_type", "concert") \
                .tag("event_name", event.get("name")) \
                .tag("location", coords) \
                .field("estimated_attendance", 0) \
                .time(utc_time)

            data_points.append(point)

        write_to_influxdb(data_points)

    current_page += 1
