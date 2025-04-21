"""
This script fetches data from the Manchester-I API and writes it to InfluxDB.
"""

import re
import requests
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
from concurrent.futures import ThreadPoolExecutor

from tools.config import INFLUXDB_URL, INFLUXDB_TOKEN, INFLUXDB_ORG, INFLUXDB_BUCKET

# Configuration
API_BASE_URL = "http://muo-backend.cs.man.ac.uk"
AUTH_TOKEN = "token-not-required"
SENSOR_FILTER = ["mcl", "car", "rigid", "artic", "bus", "avgspeed"]

HEADERS = {"Authorization": f"Bearer {AUTH_TOKEN}"}

# Utility function to extract parts of a string after the last two underscores
def extract_after_two_underscores(s):
    match = re.findall(r"(?<=__)(?!.*__).*", s)
    if match:
        return match[0]
    return s

def fetch_paginated_data(endpoint, params=None):
    if params is None:
        params = {}
    params["limit"] = 1000000
    params["offset"] = 0
    all_data = []

    while True:
        try:
            if endpoint.startswith("https"):
                response = requests.get(endpoint.replace("https", "http"), headers=HEADERS, params=params)
            elif endpoint.startswith("http"):
                response = requests.get(endpoint, headers=HEADERS, params=params)
            else:
                response = requests.get(f"{API_BASE_URL}/{endpoint}", headers=HEADERS, params=params)

            response.raise_for_status()
            data = response.json()["member"]
            all_data.extend(data)

            # Handle pagination
            if "next" not in response.json().get("meta", {}):
                break
            params["offset"] += params["limit"]
            print("Current Offset: ", params["offset"])
        except requests.exceptions.HTTPError as e:
            if response.status_code == 404:
                print(f"404 Error: {endpoint} not found. Skipping.")
                break
            else:
                print(f"HTTP Error: {e}. Skipping this endpoint.")
                break
        except Exception as e:
            print(f"Error: {e}. Skipping this endpoint.")
            break

    return all_data

def fetch_platforms():
    try:
        platforms = fetch_paginated_data("platforms")
        return [
            {
                "id": platform["@id"],
                "description": platform.get("description", ""),
                "identifier": platform.get("identifier", ""),
                "label": platform.get("label", ""),
                "geometry": platform.get("centroid", {}).get("geometry", {}),
                "hosts": platform.get("hosts", [])
            }
            for platform in platforms
            if ("traffic" in platform.get("description", "").lower() or "meteo" in platform.get("description", "").lower()) and "drakewell" in platform["@id"]
        ]
    except Exception as e:
        print(f"Error fetching platforms: {e}")
        return []

def fetch_json(url):
    try:
        response = requests.get(url.replace("https", "http"), headers=HEADERS)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        if response.status_code == 404:
            print(f"404 Error: {url} not found. Skipping.")
        else:
            print(f"HTTP Error: {e}. Skipping this URL.")
    except Exception as e:
        print(f"Error fetching JSON from {url}: {e}")
    return {}

def has_existing_data(timeseries_id, platform_id):
    try:
        with InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG) as client:
            query_api = client.query_api()
            query = f'''
                from(bucket: "{INFLUXDB_BUCKET}")
                |> range(start: 0)
                |> filter(fn: (r) => r["sensor_id"] == "{timeseries_id}" and r["platform_id"] == "{platform_id}")
                |> limit(n: 1)
            '''
            result = query_api.query(query)
            return len(result) > 0
    except Exception as e:
        print(f"Error checking existing data for {timeseries_id} on platform {platform_id}: {e}")
        return False

def fetch_observations(timeseries_id):
    return fetch_paginated_data(f"{timeseries_id}/observations")

def write_to_influxdb(data_points):
    try:
        with InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG) as client:
            write_api = client.write_api(write_options=SYNCHRONOUS)
            write_api.write(bucket=INFLUXDB_BUCKET, org=INFLUXDB_ORG, record=data_points)
    except Exception as e:
        print(f"Error writing to InfluxDB: {e}")

def process_sensor(sensor_url, platform):
    sensor = fetch_json(sensor_url)
    if not sensor:
        return

    sensor_id = sensor.get("@id", "").replace("https://muo-backend.cs.man.ac.uk/sensors/", "")
    print(f"Processing Sensor: {sensor_id}")

    for ts in sensor.get("timeseries", []):
        ts_id = extract_after_two_underscores(ts)
        if has_existing_data(ts_id, platform["identifier"]):
            print(f"Skipping TimeSeries {ts_id} on Platform {platform['identifier']} as it already has data.")
            continue

        print(f"Processing TimeSeries: {ts_id}")
        ts_property = fetch_json(ts).get("observedProperty", "unknown")
        observations = fetch_observations(ts)

        # Format data for InfluxDB
        data_points = []
        for obs in observations:
            try:
                timestamp = obs["resultTime"]
                value = float(obs["hasResult"]["value"])
                unit = obs["hasResult"]["unit"]
            except (KeyError, ValueError) as e:
                print(f"Skipping observation due to missing or invalid field: {e}")
                continue

            point = Point("Traffic" if "traffic" in platform["description"].lower() else "Meteo") \
                .tag("platform_id", platform["identifier"]) \
                .tag("platform_label", platform["label"]) \
                .tag("platform_description", platform["description"]) \
                .tag("location", platform["geometry"].get("coordinates", "")) \
                .tag("sensor_id", ts_id) \
                .tag("sensor_type", ts_property) \
                .tag("unit", unit) \
                .field("value", value) \
                .time(timestamp)

            data_points.append(point)

        if data_points:
            write_to_influxdb(data_points)

def process_platform(platform):
    for sensor_url in platform["hosts"]:
        process_sensor(sensor_url, platform)

if __name__ == "__main__":
    platforms = fetch_platforms()
    with ThreadPoolExecutor(max_workers=3) as executor:
        executor.map(process_platform, platforms)
