"""
This script trains a neural network model on the traffic data and saves the model and scalers.
"""
import ast
from datetime import datetime

import joblib
import numpy as np
from matplotlib import pyplot as plt
from sklearn.preprocessing import RobustScaler

from model.data_loader import DataLoader, query_weather_data
from model.feature_engineering import FeatureEngineering, remove_unused_columns, add_time_features
from model.model_training import ModelTrainer
from model.evaluation import Evaluator

def train_model(start_date, end_date, platform_id, sensor_id):
    loader = DataLoader()
    traffic = loader.batch_query_traffic(start_date, end_date, 7, platform_id, sensor_id)
    events = loader.query_event_data(start_date, end_date)

    lon, lat = ast.literal_eval(traffic["location"].iloc[0])
    weather = query_weather_data(start_date, end_date, lat, lon)

    loader.close()

    # === Feature Engineering ===
    fe = FeatureEngineering(events, weather)
    df = add_time_features(traffic)
    df = fe.add_event_features(df)
    #df = fe.add_weather_features(df)
    df = remove_unused_columns(df)

    # Sort, drop and keep copy
    df = df.sort_values(by="_time")
    dates = df["_time"].copy()
    df = df.drop(columns=['_time'])

    X = df.drop(columns=["value"]).values
    y = df["value"].values.reshape(-1, 1)

    # Scale data
    x_scaler = RobustScaler()
    y_scaler = RobustScaler()

    X_scaled = x_scaler.fit_transform(X)
    y_scaled = y_scaler.fit_transform(y)

    # Train-test split
    split_ratio = 0.8
    split_index = int(len(X_scaled) * split_ratio)

    X_train, X_test = X_scaled[:split_index], X_scaled[split_index:]
    y_train, y_test = y_scaled[:split_index], y_scaled[split_index:]

    dates_test = dates.iloc[split_index:]

    # Train
    trainer = ModelTrainer(model_type="FFNN")
    model = trainer.train_model(X_train, y_train)

    y_pred = model.predict(X_test)
    y_test_unscaled = y_scaler.inverse_transform(y_test).flatten()
    y_pred_unscaled = y_scaler.inverse_transform(y_pred.reshape(-1, 1)).flatten()

    y_test_unscaled = np.round(y_test_unscaled * 0.621371, 2)
    y_pred_unscaled = np.round(y_pred_unscaled * 0.621371, 2)

    evaluator = Evaluator(y_test_unscaled, y_pred_unscaled)
    metrics = evaluator.compute_metrics()

    # === Save the Model and Scalers ===
    model.save(f"trained/model_{start_date.strftime('%Y-%m-%d')}_{end_date.strftime('%Y-%m-%d')}_{platform_id}_{sensor_id}.keras")
    joblib.dump(x_scaler, f"scalers/x_scaler_{start_date.strftime('%Y-%m-%d')}_{end_date.strftime('%Y-%m-%d')}_{platform_id}_{sensor_id}.pkl")
    joblib.dump(y_scaler, f"scalers/y_scaler_{start_date.strftime('%Y-%m-%d')}_{end_date.strftime('%Y-%m-%d')}_{platform_id}_{sensor_id}.pkl")

    with open("metrics.csv", "a") as f:
        f.write(f"{start_date.strftime('%Y-%m-%d')},{end_date.strftime('%Y-%m-%d')},{platform_id},{sensor_id},{metrics['MAE']},{metrics['MSE']},{metrics['MAPE']} \n")

    start_idx_10 = int(len(dates_test) * 0.45)
    end_idx_10 = int(len(dates_test) * 0.55)

    start_idx_3 = int(len(dates_test) * 0.485)
    end_idx_3 = int(len(dates_test) * 0.515)

    fig, axes = plt.subplots(3, 1, figsize=(12, 15), sharex=False)

    # Full timeline plot
    axes[0].plot(dates_test, y_test_unscaled, label="Actual Speed")
    axes[0].plot(dates_test, y_pred_unscaled, label="Predicted Speed")
    axes[0].set_title("Actual vs Predicted Speed (Full Timeline)")
    axes[0].set_xlabel("Date-Time")
    axes[0].set_ylabel("Speed (mph)")
    axes[0].legend()
    axes[0].tick_params(axis='x', rotation=45)

    # Zoomed-in plot (Middle 10%)
    axes[1].plot(dates_test[start_idx_10:end_idx_10], y_test_unscaled[start_idx_10:end_idx_10], label="Actual Speed")
    axes[1].plot(dates_test[start_idx_10:end_idx_10], y_pred_unscaled[start_idx_10:end_idx_10], label="Predicted Speed")
    axes[1].set_title("Actual vs Predicted Speed (Middle 10% of Timeline)")
    axes[1].set_xlabel("Date-Time")
    axes[1].set_ylabel("Speed (mph)")
    axes[1].legend()
    axes[1].tick_params(axis='x', rotation=45)

    # Zoomed-in plot (Middle 3%)
    axes[2].plot(dates_test[start_idx_3:end_idx_3], y_test_unscaled[start_idx_3:end_idx_3], label="Actual Speed")
    axes[2].plot(dates_test[start_idx_3:end_idx_3], y_pred_unscaled[start_idx_3:end_idx_3], label="Predicted Speed")
    axes[2].set_title("Actual vs Predicted Speed (Middle 3% of Timeline)")
    axes[2].set_xlabel("Date-Time")
    axes[2].set_ylabel("Speed (mph)")
    axes[2].legend()
    axes[2].tick_params(axis='x', rotation=45)

    plt.tight_layout()
    plt.savefig(
        f"plots/model_{start_date.strftime('%Y-%m-%d')}_{end_date.strftime('%Y-%m-%d')}_{platform_id}_{sensor_id}.png")

if __name__ == "__main__":
    start_date = datetime(2020, 12, 1)
    end_date = datetime(2025, 2, 1)
    platform_id = "drakewell__1163"
    sensor_id = "avgspeed_nw"

    train_model(start_date, end_date, platform_id, sensor_id)
