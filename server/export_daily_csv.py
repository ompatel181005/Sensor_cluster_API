import os
import requests
from datetime import date

SERVER = "http://127.0.0.1:8000"
OUTROOT = "/data/csv"

def main():
    today = date.today().isoformat()

    devices = requests.get(f"{SERVER}/api/v1/devices").json()["devices"]
    outdir = os.path.join(OUTROOT, today)
    os.makedirs(outdir, exist_ok=True)

    for d in devices:
        url = f"{SERVER}/api/v1/devices/{d}/csv"
        r = requests.get(url, params={"day": today})
        r.raise_for_status()
        with open(os.path.join(outdir, f"{d}.csv"), "wb") as f:
            f.write(r.content)

if __name__ == "__main__":
    main()