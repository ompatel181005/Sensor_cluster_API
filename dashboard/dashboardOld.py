import requests
import pandas as pd
import streamlit as st
from datetime import date

API_BASE = "http://131.193.183.176:8000/api/v1"

st.set_page_config(page_title="Jetson Sensor Dashboard", layout="wide")

st.title("Jetson Sensor Dashboard")

# --- Load devices ---
dev_resp = requests.get(f"{API_BASE}/devices").json()
devices = dev_resp.get("devices", [])

if not devices:
    st.warning("No devices are currently reporting data.")
    st.stop()

col1, col2 = st.columns([2, 1])
with col1:
    device_id = st.selectbox("Select device", devices)
with col2:
    day = st.date_input("Select day", value=date.today())

# --- Latest reading ---
st.subheader("Latest reading")
latest = requests.get(f"{API_BASE}/devices/{device_id}/latest").json()
payload = latest.get("payload", {})

c1, c2, c3, c4 = st.columns(4)
c1.metric("Temperature (°C)", payload.get("temperature_c"))
c2.metric("Humidity (%)", payload.get("humidity_relative_percent"))
c3.metric("Pressure (hPa)", payload.get("pressure_hpa"))
c4.metric("Gas Resistance (Ω)", payload.get("gas_resistance_ohms"))

st.caption(f"Timestamp (UTC): {latest.get('timestamp')}")

# --- Historical readings for selected day ---
st.subheader("Day history")

readings_url = f"{API_BASE}/devices/{device_id}/readings"
hist = requests.get(readings_url, params={"from_date": day.isoformat(), "to_date": day.isoformat()}).json()

if not hist:
    st.info("No readings found for that date.")
else:
    df = pd.DataFrame([
        {
            "timestamp": r["timestamp"],
            "temperature_c": r["payload"].get("temperature_c"),
            "humidity_relative_percent": r["payload"].get("humidity_relative_percent"),
            "pressure_hpa": r["payload"].get("pressure_hpa"),
            "gas_resistance_ohms": r["payload"].get("gas_resistance_ohms"),
        }
        for r in hist
    ])
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    st.dataframe(df, use_container_width=True)

    st.line_chart(df.set_index("timestamp")[["temperature_c", "humidity_relative_percent", "pressure_hpa"]])

# --- CSV Download ---
st.subheader("Download CSV")

csv_url = f"{API_BASE}/devices/{device_id}/csv"
csv_bytes = requests.get(csv_url, params={"day": day.isoformat()}).content
st.download_button(
    label=f"Download {device_id} CSV for {day.isoformat()}",
    data=csv_bytes,
    file_name=f"{device_id}_{day.isoformat()}.csv",
    mime="text/csv",
)

# --- How to use (code snippet) ---
st.subheader("How to use this API")
st.markdown("### Python snippet (latest reading)")

st.code(f"""import requests

device_id = "{device_id}"
base = "{API_BASE}"

latest = requests.get(f"{{base}}/devices/{{device_id}}/latest").json()
print(latest["payload"])
""", language="python")

st.markdown("### Python snippet (download CSV for a day)")
st.code(f"""import requests

device_id = "{device_id}"
day = "{day.isoformat()}"
base = "{API_BASE}"

csv_data = requests.get(f"{{base}}/devices/{{device_id}}/csv", params={{"day": day}}).text
open(f"{{device_id}}_{{day}}.csv", "w").write(csv_data)
""", language="python")
