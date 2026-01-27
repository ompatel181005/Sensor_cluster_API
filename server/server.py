import json
from datetime import datetime, date
from typing import Dict, Any, List, Optional

from fastapi import (
    FastAPI, WebSocket, WebSocketDisconnect,
    Depends, Header, HTTPException, Query
)
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import (
    create_engine, Column, Integer, String, DateTime, Text
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import csv
import io
from fastapi.responses import StreamingResponse

# -------------------------------------------------------------------
# DATABASE SETUP (SQLite for now)
# -------------------------------------------------------------------
DATABASE_URL = "sqlite:///./sensors.db"

engine = create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Reading(Base):
    __tablename__ = "readings"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String, index=True)
    ts = Column(DateTime, index=True)
    data = Column(Text)  # JSON string


Base.metadata.create_all(bind=engine)


# -------------------------------------------------------------------
# Pydantic MODELS
# -------------------------------------------------------------------
class ReadingIn(BaseModel):
    device_id: str
    timestamp: Optional[datetime] = None  # if None, server sets now
    payload: Dict[str, Any]              # parsed sensor data


class ReadingOut(BaseModel):
    id: int
    device_id: str
    timestamp: datetime
    payload: Dict[str, Any]


class DeviceListOut(BaseModel):
    devices: List[str]


# -------------------------------------------------------------------
# SIMPLE DEVICE AUTH (per-device tokens)
# In production: move this to config or DB.
# -------------------------------------------------------------------
DEVICE_TOKENS = {
    # "device_id": "device_token"
    "jetson-lab-01": "secret-token-1",
    "jetson-lab-02": "secret-token-2",
}


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def verify_device(
    device_id: str = Header(..., alias="X-Device-ID"),
    device_token: str = Header(..., alias="X-Device-Token"),
):
    expected = DEVICE_TOKENS.get(device_id)
    if not expected or expected != device_token:
        raise HTTPException(status_code=401, detail="Invalid device credentials")
    return device_id


# -------------------------------------------------------------------
# WEBSOCKET CONNECTION MANAGER
# -------------------------------------------------------------------
class ConnectionManager:
    def __init__(self):
        # device_id -> list of WebSockets
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, device_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.setdefault(device_id, []).append(websocket)

    def disconnect(self, device_id: str, websocket: WebSocket):
        if device_id in self.active_connections:
            self.active_connections[device_id].remove(websocket)
            if not self.active_connections[device_id]:
                del self.active_connections[device_id]

    async def broadcast(self, device_id: str, message: Dict[str, Any]):
        if device_id not in self.active_connections:
            return
        dead = []
        for ws in self.active_connections[device_id]:
            try:
                await ws.send_json(message)
            except WebSocketDisconnect:
                dead.append(ws)
        for ws in dead:
            self.disconnect(device_id, ws)


manager = ConnectionManager()

# -------------------------------------------------------------------
# FASTAPI APP
# -------------------------------------------------------------------
app = FastAPI(title="Jetson Sensor Hub")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten later if you want
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -------------------------------------------------------------------
# API ENDPOINTS
# -------------------------------------------------------------------
@app.post("/api/v1/readings", status_code=201)
async def ingest_reading(
    reading: ReadingIn,
    db: Session = Depends(get_db),
    device_id: str = Depends(verify_device),
):
    # device_id from headers wins over body
    ts = reading.timestamp or datetime.utcnow()
    db_obj = Reading(
        device_id=device_id,
        ts=ts,
        data=json.dumps(reading.payload),
    )
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)

    # Broadcast for real-time consumers
    await manager.broadcast(
        device_id,
        {
            "id": db_obj.id,
            "device_id": device_id,
            "timestamp": ts.isoformat(),
            "payload": reading.payload,
        },
    )

    return {"status": "ok", "id": db_obj.id}


@app.get("/api/v1/devices", response_model=DeviceListOut)
def list_devices(db: Session = Depends(get_db)):
    rows = (
        db.query(Reading.device_id)
        .distinct()
        .order_by(Reading.device_id.asc())
        .all()
    )
    devices = [r[0] for r in rows]
    return {"devices": devices}


@app.get("/api/v1/devices/{device_id}/latest", response_model=ReadingOut)
def latest_reading(device_id: str, db: Session = Depends(get_db)):
    row = (
        db.query(Reading)
        .filter(Reading.device_id == device_id)
        .order_by(Reading.ts.desc())
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="No data for this device")

    return ReadingOut(
        id=row.id,
        device_id=row.device_id,
        timestamp=row.ts,
        payload=json.loads(row.data),
    )


@app.get("/api/v1/devices/{device_id}/readings", response_model=List[ReadingOut])
def get_readings(
    device_id: str,
    db: Session = Depends(get_db),
    from_date: Optional[date] = Query(None),
    to_date: Optional[date] = Query(None),
):
    q = db.query(Reading).filter(Reading.device_id == device_id)

    if from_date:
        start_dt = datetime.combine(from_date, datetime.min.time())
        q = q.filter(Reading.ts >= start_dt)
    if to_date:
        end_dt = datetime.combine(to_date, datetime.max.time())
        q = q.filter(Reading.ts <= end_dt)

    rows = q.order_by(Reading.ts.asc()).all()
    return [
        ReadingOut(
            id=r.id,
            device_id=r.device_id,
            timestamp=r.ts,
            payload=json.loads(r.data),
        )
        for r in rows
    ]

@app.get("/api/v1/devices/{device_id}/csv")
def export_device_csv(
    device_id: str,
    day: date = Query(..., description="YYYY-MM-DD"),
    db: Session = Depends(get_db),
):
    start_dt = datetime.combine(day, datetime.min.time())
    end_dt = datetime.combine(day, datetime.max.time())

    rows = (
        db.query(Reading)
        .filter(Reading.device_id == device_id)
        .filter(Reading.ts >= start_dt)
        .filter(Reading.ts <= end_dt)
        .order_by(Reading.ts.asc())
        .all()
    )

    def generate():
        output = io.StringIO()
        writer = csv.writer(output)

        # header
        writer.writerow(["timestamp", "temperature_c", "humidity_relative_percent", "pressure_hpa", "gas_resistance_ohms"])
        yield output.getvalue()
        output.seek(0); output.truncate(0)

        for r in rows:
            payload = json.loads(r.data)
            writer.writerow([
                r.ts.isoformat(),
                payload.get("temperature_c"),
                payload.get("humidity_relative_percent"),
                payload.get("pressure_hpa"),
                payload.get("gas_resistance_ohms"),
            ])
            yield output.getvalue()
            output.seek(0); output.truncate(0)

    filename = f"{device_id}_{day.isoformat()}.csv"
    return StreamingResponse(
        generate(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

# -------------------------------------------------------------------
# WEBSOCKET FOR REAL-TIME STREAM
# -------------------------------------------------------------------
@app.websocket("/ws/devices/{device_id}")
async def websocket_device_stream(websocket: WebSocket, device_id: str):
    # TODO: add user auth here if needed
    await manager.connect(device_id, websocket)
    try:
        while True:
            # we don't use messages from client, just keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(device_id, websocket)
