"""
This script constitues the implementation of the attendance estimation model using LLMs.

It fetches events from InfluxDB, queries the LLM for attendance estimates, and updates the events in InfluxDB with the estimates.
These can then be used as a feature in the final model.
"""

import json
import time

from influxdb_client import InfluxDBClient, Point, WritePrecision
from openai import OpenAI
from tools.config import INFLUXDB_URL, INFLUXDB_TOKEN, INFLUXDB_ORG, INFLUXDB_BUCKET, OPENROUTER_KEY

def get_events(client):
    query_api = client.query_api()
    flux_query = f'''
    from(bucket:"{INFLUXDB_BUCKET}")
      |> range(start: 2020-01-01T00:00:00Z)
      |> filter(fn: (r) => r._measurement == "Event" and r._value == 0)
    '''
    result = query_api.query(flux_query, org=INFLUXDB_ORG)
    events = []
    for table in result:
        for record in table.records:
            event = {
                "event_type": record.values.get("event_type"),
                "event_name": record.values.get("event_name"),
                "location": record.values.get("location"),
                "venue": record.values.get("venue"),
                "timestamp": record.get_time()
            }
            events.append(event)
    return events


def chunk_list(lst, chunk_size):
    for i in range(0, len(lst), chunk_size):
        yield lst[i:i + chunk_size]


def query_llm_for_estimates(llm_client, events_chunk):
    prompt = ("Please estimate the attendance for the following real events in Manchester. "
              "Return your answer as a JSON object where each key is the event ID "
              "and the value is the estimated attendance.\n\n")
    for event in events_chunk:
        prompt += f"Event ID: {event['event_id']}, Name: {event['event_name']}, Event Type: {event['event_type']}, Venue: {event['venue']}, Date: {event['timestamp']}\n"
    print(prompt)
    try:
        response = llm_client.chat.completions.create(
            model="google/gemini-2.0-flash-lite-preview-02-05:free",
            messages=[
                {"role": "system", "content": "You are an expert event planner."},
                {"role": "user", "content": prompt}
            ]
        )
        content = response.choices[0].message.content
        estimates = json.loads(content.replace("```json\n", "").replace("```", ""))
        return estimates
    except Exception as e:
        print(f"Error querying OpenAI API: {e}")
        return {}


def update_event_estimate(client, event, estimated_attendance):
    write_api = client.write_api()

    # Overwrite point
    point = (
        Point("Event")
        .tag("event_type", event["event_type"])
        .tag("location", event["location"])
        .tag("venue", event["venue"])
        .tag("event_name", event["event_name"])
        .field("estimated_attendance", estimated_attendance)
        .time(event["timestamp"], WritePrecision.NS)
    )
    write_api.write(bucket=INFLUXDB_BUCKET, org=INFLUXDB_ORG, record=point)
    print(
        f"Updated event (ID: {event['event_id']}) at timestamp {event['timestamp']} with estimated attendance: {estimated_attendance}")


def main():
    data_client = InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG)
    llm_client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=OPENROUTER_KEY,
    )

    events = get_events(data_client)
    print(f"Retrieved {len(events)} events from InfluxDB")

    for events_chunk in chunk_list(events, 20):
        for idx, event in enumerate(events_chunk):
            event["event_id"] = str(idx)
        print(f"Processing chunk of {len(events_chunk)} events")
        estimates = query_llm_for_estimates(llm_client, events_chunk)

        for event in events_chunk:
            event_id = event["event_id"]
            if event_id in estimates:
                update_event_estimate(data_client, event, estimates[event_id])
            else:
                print(f"No estimate returned for event ID {event_id}")
        # Prevent rate limiting
        time.sleep(5)


if __name__ == "__main__":
    main()
