"""
This script trains an LSTM model to predict traffic speed using historical traffic data.
"""

from datetime import datetime
import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler

from model.data_loader import DataLoader
from model.feature_engineering import FeatureEngineering, add_time_features
from model.model_training import ModelTrainer
from model.evaluation import Evaluator
import matplotlib.pyplot as plt

# Load data
start_date = datetime(2024, 1, 1)
end_date = datetime(2024, 1, 30)
sensor_id = "avgspeed_nw"
platform_id = "drakewell__1163"

loader = DataLoader()
traffic = loader.batch_query_traffic(start_date, end_date, 7, platform_id, sensor_id)
events = loader.query_event_data(start_date, end_date)

# === Feature Engineering ===
fe = FeatureEngineering(events, None)
df = add_time_features(traffic)
#df = fe.add_event_features(df)

df = df.sort_values(by="_time")
df = df.drop(columns=['_time', "result", "table", "_start", "_stop", "_measurement", "location", "platform_description", "platform_id", "platform_label", "sensor_id", "sensor_type", "unit"])

# Make a copy of the original date-time values for plotting later
feature_columns = df.drop(columns=["value"]).columns.tolist()

print("Columns after feature engineering:")
print(df.columns)

# Create time-series window data
def create_time_series_data(df, target_col, window_size=5):
    X, y = [], []
    for i in range(len(df) - window_size):
        window_data = df.iloc[i:i + window_size].values
        X.append(window_data)
        y.append(df.iloc[i + window_size][target_col])
    return np.array(X, dtype=np.float32), np.array(y, dtype=np.float32)


window_size = 60  # Use x many past observations to predict the next observation

scaler = MinMaxScaler()
scaled_data = scaler.fit_transform(df)
df = pd.DataFrame(scaled_data, columns=df.columns)

X, y = create_time_series_data(df, target_col="value", window_size=window_size)

# Train-test split
split_ratio = 0.8
split_index = int(len(X) * split_ratio)

X_train, X_test = X[:split_index], X[split_index:]
y_train, y_test = y[:split_index], y[split_index:]

print(f"Training data shape: {X_train.shape}")
print(f"Testing data shape: {X_test.shape}")

# Debug prints to verify the values and types
print("X_train sample (first window):", X_train[0])
print("y_train sample (first 5 targets):", y_train[:20])
print("X_train dtype:", X_train.dtype)
print("y_train dtype:", y_train.dtype)

trainer = ModelTrainer(model_type="LSTM")
model = trainer.train_model(X_train, y_train)

y_pred = model.predict(X_test)
evaluator = Evaluator(y_test, y_pred)
metrics = evaluator.compute_metrics()

print("Evaluation Metrics:")
print(metrics)

y_test_sensor = y_test
y_pred_sensor = y_pred

plt.figure(figsize=(12, 6))
plt.plot(y_test_sensor, label="Actual Speed")
plt.plot(y_pred_sensor, label="Predicted Speed")
plt.title(f"Actual vs Predicted Speed for Sensor" +
          f" and Direction")
plt.xlabel("Sample Index (Filtered Test Windows)")
plt.ylabel("Speed")
plt.legend()
plt.show()


def walk_forward_forecast(model, seed_window, n_steps, target_col_index=0):
    predictions = []
    current_window = seed_window.copy()

    last_hour = int(np.arcsin(current_window[-1, 3]) * 24 / (2 * np.pi))
    last_minute = int(np.arcsin(current_window[-1, 5]) * 60 / (2 * np.pi))

    for _ in range(n_steps):
        # Reshape for model prediction
        pred = model.predict(current_window[np.newaxis, :, :])
        pred_value = pred[0, 0]

        predictions.append(pred_value)

        new_row = current_window[-1].copy()
        new_row[target_col_index] = pred_value  # Update target variable

        # Advance hour and minute features
        last_minute += 5
        if last_minute >= 60:
            last_minute -= 60
            last_hour = (last_hour + 1) % 24

        new_row[3] = np.sin(2 * np.pi * last_hour / 24)
        new_row[4] = np.cos(2 * np.pi * last_hour / 24)
        new_row[5] = np.sin(2 * np.pi * last_minute / 60)
        new_row[6] = np.cos(2 * np.pi * last_minute / 60)

        current_window = np.vstack([current_window[1:], new_row])

    return np.array(predictions)


# Predict 100 steps starting from the first window in the test set
n_forecast_steps = 100
seed_window = X_test[0]

forecasted_values = walk_forward_forecast(model, seed_window, n_forecast_steps)

print("Forecasted values:", forecasted_values)

plt.figure(figsize=(12, 6))
plt.plot(range(n_forecast_steps), forecasted_values, label="Forecasted Speed")
plt.plot(range(window_size), seed_window[:, 0], label="Initial Window (real data)")
plt.title("Walk-Forward Forecast")
plt.xlabel("Time Step")
plt.ylabel("Normalized Speed")
plt.legend()
plt.show()

loader.close()
