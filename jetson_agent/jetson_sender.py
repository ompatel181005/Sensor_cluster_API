#!/usr/bin/env python3
import os
import subprocess
from datetime import datetime

import requests

SERVER_URL = os.getenv("SERVER_URL", "http://131.193.183.176:8000/api/v1/readings")
DEVICE_ID = os.getenv("DEVICE_ID", "jetson-lab-01")
DEVICE_TOKEN = os.getenv("DEVICE_TOKEN", "secret-token-1")

LOG_FILE = "/var/log/sensor_readings.txt"
SENSOR_SCRIPT = "/usr/local/bin/read_sensor_inputs.sh"


def read_sensor_block() -> str:
    # Run sensor script as root via sudo
    subprocess.run(["sudo", SENSOR_SCRIPT], check=True)

    # Read last 4 lines from log (one per sensor)
    result = subprocess.run(
        ["tail", "-n", "4", LOG_FILE],
        stdout=subprocess.PIPE,
        universal_newlines=True,  # Python 3.6-friendly
        check=True,
    )
    return result.stdout.strip()


def parse_raw_block(raw_block: str):
    """
    Convert the raw sysfs-style lines into structured JSON.
    Example line:
    /sys/.../iio:device1/in_temp_input:23590
    """
    sensors = {}

    for line in raw_block.splitlines():
        line = line.strip()
        if not line:
            continue

        # Split on the LAST ":" because the path contains "iio:device1"
        try:
            path, value_str = line.rsplit(":", 1)
        except ValueError:
            # malformed line
            continue

        name = path.split("/")[-1]  # e.g. "in_temp_input"
        value_str = value_str.strip()

        try:
            value = float(value_str)
        except ValueError:
            value = value_str

        sensors[name] = value

    out = {}

    # Map to nicer names; adjust scaling based on your sensor's datasheet
    if "in_humidityrelative_input" in sensors:
        out["humidity_relative_percent"] = sensors["in_humidityrelative_input"]

    if "in_pressure_input" in sensors:
        out["pressure_hpa"] = sensors["in_pressure_input"]  # name it clearly

    if "in_resistance_input" in sensors:
        out["gas_resistance_ohms"] = sensors["in_resistance_input"]

    if "in_temp_input" in sensors:
        # Usually milli-deg C; divide by 1000 if that matches your sensor
        out["temperature_c"] = sensors["in_temp_input"] / 1000.0

    # Keep raw mapping for debugging
    out["_raw"] = sensors

    return out


def send_reading():
    raw_block = read_sensor_block()
    print("RAW BLOCK:\n", raw_block)

    parsed = parse_raw_block(raw_block)
    print("PARSED PAYLOAD:", parsed)

    payload = {
        "device_id": DEVICE_ID,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "payload": parsed,
    }

    headers = {
        "X-Device-ID": DEVICE_ID,
        "X-Device-Token": DEVICE_TOKEN,
    }

    print("POSTING TO:", SERVER_URL)
    print("HEADERS:", headers)
    print("PAYLOAD JSON:", payload)

    try:
        resp = requests.post(SERVER_URL, json=payload, headers=headers, timeout=5)
        print("RESPONSE:", resp.status_code, resp.text)
        resp.raise_for_status()
    except Exception as e:
        print("ERROR DURING POST:", repr(e))
        raise


if __name__ == "__main__":
    send_reading()