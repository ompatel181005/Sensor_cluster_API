Jetson Sensor Hub

Overview

Jetson Sensor Hub is a local-network sensor telemetry platform for collecting, storing, exporting, and visualizing sensor data from multiple NVIDIA Jetson devices.

Each Jetson device reads hardware sensors and periodically sends structured sensor data to a central FastAPI server. The server stores the data, exposes REST APIs, supports per-day CSV export, and provides a simple dashboard for visualization.

This project is designed for labs, research environments, and internal sensor networks.

---

Features

* Jetson devices push sensor data at a fixed interval (e.g., every second)
* Central FastAPI server for ingestion and storage
* Per-device authentication using HTTP headers
* Query sensor data by device and date
* Export CSV files per device per day
* Structured JSON payloads
* UTC timestamps for consistency
* Optional WebSocket streaming for real-time use
* Streamlit dashboard for visualization and downloads

---

Architecture

Jetson devices run a Python agent that:

* reads sensor values from the system
* parses raw sensor output into structured JSON
* sends data to the server via HTTP POST

The FastAPI server:

* authenticates devices
* stores readings in a database
* exposes REST endpoints for data access
* optionally streams data using WebSockets
* generates CSV exports

Users interact with the system via:

* REST API calls
* CSV downloads
* a Streamlit dashboard

---

Security Model

Each Jetson device authenticates using HTTP headers:

X-Device-ID
X-Device-Token

The server validates these headers before accepting data.

This model is intended for trusted local networks. User authentication for read access is not enabled by default.

---

Repository Structure

server/
Contains the FastAPI backend, database logic, API endpoints, and CSV export functionality.

jetson_agent/
Contains the Python script that runs on each Jetson and sends sensor data.

dashboard/
Contains the Streamlit dashboard for visualization and CSV downloads.

client_examples/
Contains example Python scripts demonstrating API usage.

systemd/
Contains example systemd service and timer files.

---

Server Setup

1. Create a virtual environment
   python3 -m venv myenv
   source myenv/bin/activate

2. Install dependencies
   pip install -r requirements.txt

3. Run the server
   uvicorn server:app --host 0.0.0.0 --port 8000

4. API documentation (Swagger UI)
   [http://HOST:8000/docs](http://HOST:8000/docs)

5. To run in the background, install and enable the provided systemd service.

---

Jetson Agent Setup

1. Copy jetson_sender.py to the Jetson device
2. Install dependencies
   pip3 install requests
3. Configure passwordless sudo access for the sensor read script
4. Set DEVICE_ID, DEVICE_TOKEN, and SERVER_URL
5. Enable the systemd service and timer to send data automatically

---

API Endpoints

Base URL:
[http://HOST:8000](http://HOST:8000)

All API endpoints are prefixed with:
/api/v1

---

POST /api/v1/readings

Description:
Ingest a new sensor reading from a Jetson device.

Authentication:
Required
Headers:
X-Device-ID
X-Device-Token

Request body (JSON):

{
"device_id": "jetson-lab-01",
"timestamp": "2025-12-05T19:15:54Z",
"payload": {
"temperature_c": 23.5,
"humidity_relative_percent": 12.7,
"pressure_hpa": 989.5,
"gas_resistance_ohms": 34438
}
}

Response:
201 Created

---

GET /api/v1/devices

Description:
List all devices that have reported data.

Response:

{
"devices": ["jetson-lab-01", "jetson-lab-02"]
}

---

GET /api/v1/devices/{device_id}/latest

Description:
Fetch the most recent sensor reading for a device.

Example:
GET /api/v1/devices/jetson-lab-01/latest

Response:

{
"id": 7,
"device_id": "jetson-lab-01",
"timestamp": "2025-12-05T19:15:54Z",
"payload": {
"temperature_c": 23.54,
"humidity_relative_percent": 12.736,
"pressure_hpa": 989.56,
"gas_resistance_ohms": 34438
}
}

---

GET /api/v1/devices/{device_id}/readings

Description:
Fetch historical readings for a device.

Query parameters:
from_date=YYYY-MM-DD
to_date=YYYY-MM-DD

Example:
GET /api/v1/devices/jetson-lab-01/readings?from_date=2025-12-05&to_date=2025-12-05

Response:
List of readings with timestamps and payloads.

---

GET /api/v1/devices/{device_id}/csv

Description:
Download a CSV file containing all readings for a device on a given day.

Query parameters:
day=YYYY-MM-DD

Example:
GET /api/v1/devices/jetson-lab-01/csv?day=2025-12-05

Response:
CSV file download.

---

WebSocket Endpoint (Optional)

WebSockets are optional and not required for standard operation.

Endpoint:
ws://HOST:8000/ws/devices/{device_id}

Description:
Streams live sensor readings to connected clients in real time.

Useful for:

* live dashboards
* alerting systems
* low-latency visualization

---

Dashboard

The Streamlit dashboard provides:

* device selection
* date selection
* latest sensor values
* time-series plots
* CSV download buttons
* example API usage code

Run the dashboard with:
streamlit run dashboard.py --server.port 8501 --server.address 0.0.0.0

Access it at:
[http://HOST:8501](http://HOST:8501)

---

Timestamps

All timestamps are generated and stored in UTC. Clients should convert timestamps to local time when displaying data.

---

Public Repository Safety

This repository can be public, but before publishing:

* Replace real IP addresses with placeholders such as HOST or <SERVER_IP>
* Remove hardcoded device tokens
* Use environment variables for secrets
* Do not commit credentials or internal infrastructure details

---

License

MIT License

