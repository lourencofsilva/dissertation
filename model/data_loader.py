"""
This module contains the DataLoader class, which is responsible for querying data from InfluxDB and the Open-Meteo API.

The module is used by many scripts in the project to fetch traffic, event, and weather data.
"""

from datetime import timedelta

import requests
from influxdb_client import InfluxDBClient
import pandas as pd

from tools.config import INFLUXDB_URL, INFLUXDB_TOKEN, INFLUXDB_ORG, INFLUXDB_BUCKET, WEATHER_URL

def query_weather_data(start_date, stop_date, lat, lon):
    endpoint = WEATHER_URL.format(lat=lat, lon=lon, start_date=start_date.strftime("%Y-%m-%d"), end_date=stop_date.strftime("%Y-%m-%d"))
    response = requests.get(endpoint)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Failed to fetch weather data: {response.status_code}")
        return None


class DataLoader:
    def __init__(self):
        self.client = InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG)
        self.query_api = self.client.query_api()

    def query_event_data(self, start_time, stop_time):
        query = f'''
        from(bucket: "{INFLUXDB_BUCKET}")
        |> range(start: {start_time.isoformat()}Z, stop: {stop_time.isoformat()}Z)
        |> filter(fn: (r) => r["_measurement"] == "Event")
        |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
        '''
        result = self.query_api.query_data_frame(query)
        return result

    def query_traffic_data(self, start_time, stop_time, platform_id, sensor_id):
        query = f'''
        from(bucket: "{INFLUXDB_BUCKET}")
        |> range(start: {start_time.isoformat()}Z, stop: {stop_time.isoformat()}Z)
        |> filter(fn: (r) => r["_measurement"] == "Traffic" and r["sensor_type"] == "vehicle-speed" and r["sensor_id"] == "{sensor_id}" and r["platform_id"] == "{platform_id}")
        |> filter(fn: (r) => r["_value"] > 0)
        |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
        '''
        result = self.query_api.query_data_frame(query)
        return result

    def lookup_sensor_location(self, platform_id, sensor_id):
        query = f'''
                from(bucket: "{INFLUXDB_BUCKET}")
                |> range(start:-365d)
                |> filter(fn: (r) => r["_measurement"] == "Traffic" and r["sensor_type"] == "vehicle-speed" and r["sensor_id"] == "{sensor_id}" and r["platform_id"] == "{platform_id}")
                |> filter(fn: (r) => r["_value"] > 0)
                |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
                '''
        result = self.query_api.query_data_frame(query)
        return result["location"].iloc[0]

    def batch_query_traffic(self, start_date, end_date, batch_days, platform_id, sensor_id):
        all_data = []
        current_date = start_date

        while current_date < end_date:
            next_batch = current_date + timedelta(days=batch_days)
            if next_batch > end_date:
                next_batch = end_date

            print(f"Querying from {current_date} to {next_batch}...")

            data = self.query_traffic_data(current_date, next_batch, platform_id, sensor_id)
            if data is not None:
                all_data.append(data)

            current_date = next_batch

        return pd.concat(all_data, ignore_index=True) if all_data else None

    def close(self):
        self.client.close()
