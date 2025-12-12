import requests

BASE = "http://131.193.183.176:8000/api/v1"
devices = requests.get(f"{BASE}/devices").json()["devices"]
print("Devices:", devices)

for d in devices:
    latest = requests.get(f"{BASE}/devices/{d}/latest").json()
    print(d, latest["timestamp"], latest["payload"])
