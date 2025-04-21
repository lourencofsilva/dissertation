"""
This script is used to batch train models for every sensor in the database that has over 80% of the expected data points.
"""
from datetime import datetime

from model.data_loader import DataLoader
from model.train_model_nn import train_model

loader = DataLoader()

start_date = datetime(2020, 12, 1)
end_date = datetime(2025, 2, 1)
minutes_per_day = 24 * 60 / 5  # 5-minute intervals per day
total_expected_points = (end_date - start_date).days * minutes_per_day
threshold = 0.8 * total_expected_points  # 80% threshold

traffic_query = f'''
from(bucket: "manchester-i")
  |> range(start: {start_date.isoformat()}Z, stop: {end_date.isoformat()}Z)
  |> filter(fn: (r) => r._measurement == "Traffic" and r.sensor_type == "vehicle-speed")
  |> filter(fn: (r) => r["_value"] > 0)
  |> group(columns: ["platform_id", "sensor_id"])
  |> count()
'''

traffic_results = loader.query_api.query(traffic_query)
loader.close()

for table in traffic_results:
    for record in table.records:
        # Threshold makes sure the sensor has over 80% data points for our required period - removes bad sensors
        if record["_value"] >= threshold and record["platform_id"] >= "drakewell__1429":
            print("TRAINING MODEL FOR", record["platform_id"], record["sensor_id"])
            train_model(start_date, end_date, record["platform_id"], record["sensor_id"])
