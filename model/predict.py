"""
This script is used to generate predictions from the trained models for a given date range and sensor.
Used for further analysis, visualisation and simulation purposes.
"""

import ast
from datetime import datetime
import joblib
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from tensorflow.keras.models import load_model

from model.data_loader import DataLoader, query_weather_data
from model.feature_engineering import FeatureEngineering, remove_unused_columns, add_time_features


def predict_model(start_date, end_date, platform_id, sensor_id, model_date_range=None):
    # Create a dataframe with rows for every 5 minutes in the prediction period.
    time_index = pd.date_range(start=start_date, end=end_date, freq='5T')
    traffic = pd.DataFrame({'_time': time_index})

    # Dummy target column
    traffic['value'] = 0.0

    loader = DataLoader()
    events = loader.query_event_data(start_date, end_date)
    traffic['location'] = loader.lookup_sensor_location(platform_id, sensor_id)

    lon, lat = ast.literal_eval(traffic["location"].iloc[0])
    weather = query_weather_data(start_date, end_date, lat, lon)
    loader.close()

    # --- Feature Engineering ---
    fe = FeatureEngineering(events, weather)
    df = add_time_features(traffic)
    df = fe.add_event_features(df)
    # df = fe.add_weather_features(df)
    df = remove_unused_columns(df)

    # Sort and keep a copy
    df = df.sort_values(by="_time")
    dates = df["_time"].copy()
    df = df.drop(columns=['_time'])

    X = df.drop(columns=["value"]).values

    if model_date_range is None:
        model_start_date = start_date.strftime('%Y-%m-%d')
        model_end_date = end_date.strftime('%Y-%m-%d')
    else:
        model_start_date, model_end_date = model_date_range

    model_path = f"trained/model_{model_start_date}_{model_end_date}_{platform_id}_{sensor_id}.keras"
    x_scaler_path = f"scalers/x_scaler_{model_start_date}_{model_end_date}_{platform_id}_{sensor_id}.pkl"
    y_scaler_path = f"scalers/y_scaler_{model_start_date}_{model_end_date}_{platform_id}_{sensor_id}.pkl"

    model = load_model(model_path)
    x_scaler = joblib.load(x_scaler_path)
    y_scaler = joblib.load(y_scaler_path)

    # Scale and predict
    X_scaled = x_scaler.transform(X)
    y_pred_scaled = model.predict(X_scaled)
    y_pred = y_scaler.inverse_transform(y_pred_scaled).flatten()

    y_pred = np.round(y_pred * 0.621371, 2) # Convert m/s to mph

    output_df = traffic.copy()
    output_df["predicted_speed"] = y_pred
    output_df["timestamp"] = dates
    output_csv = f"predictions/predictions_{start_date.strftime('%Y-%m-%d')}_{end_date.strftime('%Y-%m-%d')}_{platform_id}_{sensor_id}.csv"
    output_df.to_csv(output_csv, index=False)

    plt.figure(figsize=(12, 6))
    plt.plot(dates, y_pred, label="Predicted Speed")
    plt.title("Predicted Speed Over Time")
    plt.xlabel("Date-Time")
    plt.ylabel("Speed (mph)")
    plt.xticks(rotation=45)
    plt.legend()
    plt.tight_layout()
    plot_filename = f"plots/prediction_{start_date.strftime('%Y-%m-%d')}_{end_date.strftime('%Y-%m-%d')}_{platform_id}_{sensor_id}.png"
    plt.savefig(plot_filename)

    print(f"Predictions saved to {output_csv} and plot saved to {plot_filename}")


if __name__ == "__main__":
    # Prediction range
    dates = [datetime(2024, 3, 31),
             datetime(2024, 5, 19),
             datetime(2024, 9, 14),
             datetime(2024, 10, 5)]


    sensors = [("drakewell__1163", "avgspeed_nw"), ("drakewell__1163", "avgspeed_se"), ("drakewell__1418", "avgspeed_e"), ("drakewell__1418", "avgspeed_w")]

    model_date_range = ("2020-12-01", "2025-02-01")

    for start_date in dates:
        try:
            end_date = start_date.replace(day=start_date.day + 1)
        except ValueError:
            if start_date.month == 12:
                end_date = start_date.replace(year=start_date.year + 1, month=1, day=1)
            else:
                end_date = start_date.replace(month=start_date.month + 1, day=1)

        for platform_id, sensor_id in sensors:
            predict_model(start_date, end_date, platform_id, sensor_id, model_date_range)
