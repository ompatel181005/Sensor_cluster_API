import json
import websocket

DEVICE_ID = "jetson-lab-01"
WS_URL = f"ws://131.193.183.176:8000/ws/devices/{DEVICE_ID}"

def on_message(ws, msg):
    data = json.loads(msg)
    print("LIVE:", data["timestamp"], data["payload"])

ws = websocket.WebSocketApp(WS_URL, on_message=on_message)
ws.run_forever()
