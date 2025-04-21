"""
Project configuration file.

This file contains the configuration settings for the project. It is used by
the various scripts in the project to access keys and other settings.
"""

INFLUXDB_URL = ""
INFLUXDB_TOKEN = ""
INFLUXDB_ORG = ""
INFLUXDB_BUCKET = ""

WEATHER_URL = "https://archive-api.open-meteo.com/v1/archive?latitude={lat}&longitude={lon}&start_date={start_date}&end_date={end_date}&hourly=relative_humidity_2m,precipitation,wind_speed_10m"
OPENROUTER_KEY = ""
