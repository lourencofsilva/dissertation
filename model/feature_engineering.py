"""
This module contains the FeatureEngineering class which is responsible for adding new features to the dataset.

The module is used by the train_model_nn.py script to add time, weather, and event features to the traffic data.
"""

import ast
import pandas as pd
import numpy as np
from geopy.distance import geodesic
from joblib import Parallel, delayed
import multiprocessing

def remove_unused_columns(df):
    columns_to_drop = ["_start", "_stop", "result", "table", "platform_description",
                         "sensor_type", "platform_label", "unit", "_measurement",
                         "location", "platform_id", "sensor_id"]
    df.drop(columns=columns_to_drop, inplace=True, errors='ignore')
    return df

def add_time_features(df):
    # Convert the _time column to datetime
    df["_time"] = pd.to_datetime(df["_time"])

    # Extract non-cyclic time features
    df['year'] = df['_time'].dt.year
    df['day'] = df['_time'].dt.day

    # Cyclic encoding of time features
    df['hour_sin'] = np.sin(2 * np.pi * df['_time'].dt.hour / 24)
    df['hour_cos'] = np.cos(2 * np.pi * df['_time'].dt.hour / 24)

    df['minute_sin'] = np.sin(2 * np.pi * df['_time'].dt.minute / 60)
    df['minute_cos'] = np.cos(2 * np.pi * df['_time'].dt.minute / 60)

    df['weekday_sin'] = np.sin(2 * np.pi * df['_time'].dt.weekday / 7)
    df['weekday_cos'] = np.cos(2 * np.pi * df['_time'].dt.weekday / 7)

    df['month_sin'] = np.sin(2 * np.pi * (df['_time'].dt.month - 1) / 12)
    df['month_cos'] = np.cos(2 * np.pi * (df['_time'].dt.month - 1) / 12)

    return df


class FeatureEngineering:
    def __init__(self, event_data, weather_data):
        self.event_data = event_data
        self.weather_data = weather_data

    def add_weather_features(self, df):
        weather_df = pd.DataFrame(self.weather_data["hourly"])
        weather_df["time"] = pd.to_datetime(weather_df["time"]).dt.tz_localize(None)
        df["_time"] = pd.to_datetime(df["_time"]).dt.tz_localize(None)

        # Sort by time
        weather_df.sort_values("time", inplace=True)
        df.sort_values("_time", inplace=True)

        df = pd.merge_asof(df, weather_df, left_on="_time", right_on="time", direction="nearest")
        df.drop(columns=["time"], inplace=True)

        df.rename(columns={
            "relative_humidity_2m": "wth_rel_hum",
            "precipitation": "wth_precip",
            "wind_speed_10m": "wth_wind"
        }, inplace=True)

        return df


    def add_event_features(self, df):
        # Event feature engineering parameters
        TIME_WINDOW_HOURS = 12  # look for events within 12 hours before/after
        DISTANCE_WINDOW_KM = 3  # look for events within 3 km
        DEFAULT_DISTANCE = 100.0
        DEFAULT_TIME_DIFF = 100.0

        # If no events in time-frame
        if self.event_data.empty:
            df["event_min_distance"] = DEFAULT_DISTANCE
            df["event_min_time_diff"] = DEFAULT_TIME_DIFF
            df["event_type"] = None
            df["has_event"] = 0
            df = pd.get_dummies(df, columns=["event_type"], prefix="evt")
            for col in ["evt_match", "evt_concert"]:
                if col not in df.columns:
                    df[col] = 0
            print("NONE")
            return df

        # --- Precompute event data arrays ---
        event_times = self.event_data["_time"].to_numpy(dtype="datetime64[ns]")

        event_locations = self.event_data["location"].apply(ast.literal_eval).tolist()
        event_locations = np.array(event_locations)

        event_types = self.event_data["event_type"].to_numpy()

        # event_values = self.event_data["estimated_attendance"].to_numpy()

        def compute_event_features(row):
            row_time = row["_time"]
            row_loc = ast.literal_eval(row["location"])

            # Swap order as our data is (lat, lon) but geopy expects (lon, lat)
            if len(row_loc) == 2:
                row_loc = (row_loc[1], row_loc[0])

            row_time_np = np.datetime64(row_time)

            # Compute time differences
            time_diffs = (event_times - row_time_np) / np.timedelta64(1, 'h')

            # Filter events within the time window.
            valid_time_mask = (time_diffs >= -TIME_WINDOW_HOURS) & (time_diffs <= TIME_WINDOW_HOURS)
            if not np.any(valid_time_mask):
                return pd.Series({
                    "event_min_distance": DEFAULT_DISTANCE,
                    "event_min_time_diff": DEFAULT_TIME_DIFF,
                    "event_type": None,
                    "has_event": 0,
                })

            # For events passing filter
            valid_time_diffs = time_diffs[valid_time_mask]
            valid_event_locations = event_locations[valid_time_mask]
            valid_event_types = event_types[valid_time_mask]
            # valid_event_values = event_values[valid_time_mask]

            distances = np.array([
                geodesic(row_loc, tuple(loc)).km
                for loc in valid_event_locations
            ])

            valid_distance_mask = distances <= DISTANCE_WINDOW_KM
            if not np.any(valid_distance_mask):
                return pd.Series({
                    "event_min_distance": DEFAULT_DISTANCE,
                    "event_min_time_diff": DEFAULT_TIME_DIFF,
                    "event_type": None,
                    "has_event": 0,
                })

            valid_distances = distances[valid_distance_mask]
            valid_filtered_time_diffs = valid_time_diffs[valid_distance_mask]
            valid_filtered_event_types = valid_event_types[valid_distance_mask]
            # valid_filtered_event_values = valid_event_values[valid_distance_mask]

            # Find the event with the minimum distance.
            min_idx = np.argmin(abs(valid_filtered_time_diffs))
            min_distance = valid_distances[min_idx]
            min_time_diff = valid_filtered_time_diffs[min_idx]
            chosen_event_type = valid_filtered_event_types[min_idx]
            # est_attendance = valid_filtered_event_values[min_idx]

            return pd.Series({
                "event_min_distance": min_distance,
                "event_min_time_diff": min_time_diff,
                "event_type": chosen_event_type,
                "has_event": min_distance != DEFAULT_DISTANCE,
            })

        # Run all this processing in parallel on multiple cores for optimised performance
        num_cores = multiprocessing.cpu_count()
        df_chunks = np.array_split(df, num_cores)
        results = Parallel(n_jobs=num_cores, backend='loky')(
            delayed(lambda chunk: chunk.apply(compute_event_features, axis=1))(chunk)
            for chunk in df_chunks
        )
        event_features = pd.concat(results)

        # Merge the new features with the original DataFrame.
        df = pd.concat([df, event_features], axis=1)
        df = pd.get_dummies(df, columns=["event_type"], prefix="evt")
        for col in ["evt_match", "evt_concert"]:
            if col not in df.columns:
                df[col] = 0
        return df
