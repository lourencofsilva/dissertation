"""
Simple ARIMA model for traffic speed forecasting
"""

import pandas as pd
import matplotlib.pyplot as plt
from statsmodels.tsa.arima.model import ARIMA

from model.data_loader import DataLoader

dataloader = DataLoader()
query_api = dataloader.query_api

# Query traffic data
traffic_source = 'drakewell-1163'
traffic_query = f"""
from(bucket:"manchester-i")
  |> range(start:-365d)
  |> filter(fn: (r) => r._measurement == "Traffic" and r.platform_id == "drakewell__1163" and r.sensor_type == "vehicle-speed" and r.sensor_id == "avgspeed_nw")
  |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
"""
traffic_data = query_api.query_data_frame(traffic_query)

traffic_data['_time'] = pd.to_datetime(traffic_data['_time'])
traffic_data.set_index('_time', inplace=True)
speed_data = traffic_data[traffic_data['value'] > 0]

ts = speed_data["value"]

# train-test split
train_size = int(len(ts) * 0.8)
train, test = ts.iloc[:train_size], ts.iloc[train_size:]

# Simple ARIMA model
model = ARIMA(train, order=(1, 1, 1))
model_fit = model.fit()

# Forecast
forecast_steps = len(test)
forecast = model_fit.forecast(steps=forecast_steps)

plt.figure(figsize=(12, 6))
plt.plot(train.index, train, label="Train", color="blue")
plt.plot(test.index, test, label="Test", color="green")
plt.plot(test.index, forecast, label="Forecast", color="red", linestyle="--")
plt.title("ARIMA Forecast for Traffic Speed (NW)", fontsize=14)
plt.xlabel("Time", fontsize=12)
plt.ylabel("Traffic Speed", fontsize=12)
plt.legend()
plt.grid(True)
plt.tight_layout()
plt.show()

print(model_fit.summary())
