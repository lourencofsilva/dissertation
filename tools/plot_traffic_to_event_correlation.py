"""
This script plots the traffic data around an event at a specific venue and the traffic data for the same time window
on the same and next day.

Used for visualizing the traffic data around events to understand the correlation between traffic and events.
"""

from influxdb_client import InfluxDBClient
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.dates import DateFormatter

from tools.config import INFLUXDB_URL, INFLUXDB_TOKEN, INFLUXDB_ORG

client = InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG)
query_api = client.query_api()

venue = 'Etihad'
event_query = f"""
from(bucket:"manchester-i") |> range(start:-100d) |> filter(fn: (r) => r._measurement == "Event" and r.venue == "{venue}")
"""
event_data = query_api.query_data_frame(event_query)

event_data['_time'] = pd.to_datetime(event_data['_time'])
event_data.set_index('_time', inplace=True)

traffic_source = 'drakewell-1163'
traffic_query = f"""
from(bucket:"manchester-i") |> range(start:-100d) |> filter(fn: (r) => r._measurement == "Traffic" and r.platform_id == "drakewell__1163" and r.sensor_id == "avgspeed_nw")
"""
traffic_data = query_api.query_data_frame(traffic_query)

# Convert traffic data to DataFrame
traffic_data['_time'] = pd.to_datetime(traffic_data['_time'])
traffic_data.set_index('_time', inplace=True)

# Iterate over event times to generate individual plots
for event_time in event_data.index:
    start_time = event_time - pd.Timedelta(hours=12)
    end_time = event_time + pd.Timedelta(hours=12)

    next_day_start = start_time + pd.Timedelta(days=1)
    next_day_end = end_time + pd.Timedelta(days=1)

    # Filter
    traffic_window = traffic_data[(traffic_data.index >= start_time) & (traffic_data.index <= end_time)]
    traffic_next_day = traffic_data[(traffic_data.index >= next_day_start) & (traffic_data.index <= next_day_end)]

    # Plot traffic data for the event window
    plt.figure(figsize=(12, 6))
    plt.plot(traffic_window.index, traffic_window['_value'], label='Traffic Speed (Event Day)', marker='o', linewidth=2)
    plt.axvline(x=event_time, color='red', linestyle='--', label='Event Time')
    plt.title(f'Traffic Data Around Event at {venue} (12-Hour Window)', fontsize=14)
    plt.xlabel('Time', fontsize=12)
    plt.ylabel('Traffic Speed (km/h)', fontsize=12)
    plt.legend(fontsize=12)
    plt.grid(True)
    plt.tight_layout()
    plt.gca().xaxis.set_major_formatter(DateFormatter("%Y-%m-%d %H:%M"))
    plt.xticks(rotation=45)
    plt.show()

    # Plot traffic data for the next day
    plt.figure(figsize=(12, 6))
    plt.plot(traffic_next_day.index, traffic_next_day['_value'], label='Traffic Speed (Next Day)', marker='s',
             linewidth=2, color='orange')
    plt.axvline(x=next_day_start + pd.Timedelta(hours=12), color='blue', linestyle='--',
                label='Midpoint of Next Day Window')
    plt.title(f'Traffic Data After Event at {venue} (12-Hour Window, Next Day)', fontsize=14)
    plt.xlabel('Time', fontsize=12)
    plt.ylabel('Traffic Speed (km/h)', fontsize=12)
    plt.legend(fontsize=12)
    plt.grid(True)
    plt.tight_layout()
    plt.gca().xaxis.set_major_formatter(DateFormatter("%Y-%m-%d %H:%M"))
    plt.xticks(rotation=45)
    plt.show()
