"""
WinPulse - FastAPI Backend
Routes: anomalies, metrics, system status, websocket
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from sqlalchemy.orm import Session
from sqlalchemy import desc, and_
from datetime import datetime, timedelta
from typing import List, Optional, Dict
from pydantic import BaseModel
import logging
import os
import asyncio
from dotenv import load_dotenv
from functools import wraps

from backend.models import get_db, init_db, User, Event, Anomaly, CorrelatedAnomaly, SystemStatus

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Suppress verbose database warnings
logging.getLogger("backend.models").setLevel(logging.ERROR)

# ============ AUTHENTICATION ============

def get_current_user_id(user_id: int = Query(1)) -> int:
    """
    Extract user_id from query parameter.
    In production, replace this with JWT token validation.
    Example JWT implementation:
    
    from fastapi import Header
    from jose import JWTError, jwt
    
    SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key")
    ALGORITHM = "HS256"
    
    def get_current_user_id(authorization: str = Header(None)):
        if not authorization:
            raise HTTPException(status_code=401, detail="Missing authorization header")
        try:
            scheme, token = authorization.split()
            if scheme.lower() != "bearer":
                raise HTTPException(status_code=401, detail="Invalid authentication scheme")
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            user_id = payload.get("sub")
            if user_id is None:
                raise HTTPException(status_code=401, detail="Invalid token")
            return int(user_id)
        except JWTError:
            raise HTTPException(status_code=401, detail="Invalid token")
    """
    return user_id

# ============ PYDANTIC SCHEMAS ============

class AnomalyResponse(BaseModel):
    id: int
    metric: str
    agent: str
    actual_value: float
    expected_value: Optional[float]
    z_score: float
    p_value: float
    confidence: float
    severity: str
    timestamp: datetime
    class Config:
        from_attributes = True

class CorrelatedAnomalyResponse(BaseModel):
    id: int
    anomaly_ids: List[int]
    agents_involved: List[str]
    anomaly_count: int
    correlation_score: float
    explanation: Optional[str]
    timestamp: datetime
    class Config:
        from_attributes = True

# ============ HELPERS ============

def _get_system_status(db: Session, user_id: int) -> dict:
    status = db.query(SystemStatus).filter(
        SystemStatus.user_id == user_id
    ).order_by(desc(SystemStatus.updated_at)).first()
    cutoff = datetime.utcnow() - timedelta(hours=24)
    recent_anomalies = db.query(Anomaly).filter(
        and_(Anomaly.user_id == user_id, Anomaly.timestamp >= cutoff)
    ).all()
    high_severity = len([a for a in recent_anomalies if a.severity == "high"])
    risk_score = min(100, (high_severity * 30) + (len(recent_anomalies) * 2))
    return {
        "warmup_complete": status.warmup_complete if status else False,
        "total_anomalies_24h": len(recent_anomalies),
        "high_severity_count": high_severity,
        "risk_score": risk_score,
        "agents_active": status.agents_active if status else {}
    }

def _get_agent_status(db: Session, user_id: int) -> list:
    agents = ["process_resource", "network", "session", "application", "filesystem", "device", "system_events"]
    cutoff = datetime.utcnow() - timedelta(hours=24)
    results = []
    for agent_name in agents:
        latest = db.query(Event).filter(
            and_(Event.user_id == user_id, Event.agent == agent_name)
        ).order_by(desc(Event.timestamp)).first()
        count = db.query(Event).filter(
            and_(Event.user_id == user_id, Event.agent == agent_name, Event.timestamp >= cutoff)
        ).count()
        last_ts = None
        is_active = False
        if latest:
            last_ts = latest.timestamp
            is_active = (datetime.utcnow() - latest.timestamp) < timedelta(minutes=5)
        results.append({
            "agent_name": agent_name,
            "is_active": is_active,
            "last_event_timestamp": last_ts,
            "event_count_24h": count
        })
    return results

def _get_warmup_progress(db: Session, user_id: int) -> dict:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    elapsed = datetime.utcnow() - user.created_at
    days_elapsed = elapsed.days
    total_events = db.query(Event).filter(Event.user_id == user_id).count()
    completion_time = user.created_at + timedelta(days=7)
    return {
        "warmup_complete": days_elapsed >= 7,
        "days_elapsed": days_elapsed,
        "days_remaining": max(0, 7 - days_elapsed),
        "total_events_collected": total_events,
        "estimated_completion": completion_time.isoformat()
    }

# ============ WEBSOCKET MANAGER ============

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[int, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: int):
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(websocket)
        logger.info(f"User {user_id} connected via WebSocket")

    def disconnect(self, websocket: WebSocket, user_id: int):
        if user_id in self.active_connections:
            self.active_connections[user_id].remove(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]

    async def broadcast_anomaly(self, user_id: int, anomaly: Dict):
        if user_id not in self.active_connections:
            return
        message = {
            "type": "anomaly",
            "timestamp": datetime.utcnow().isoformat(),
            "data": anomaly
        }
        disconnected = []
        for ws in self.active_connections[user_id]:
            try:
                await ws.send_json(message)
            except Exception:
                disconnected.append(ws)
        for ws in disconnected:
            self.disconnect(ws, user_id)

    async def broadcast_status(self, user_id: int, status: Dict):
        """Send periodic status updates to connected clients"""
        if user_id not in self.active_connections:
            return
        message = {
            "type": "status",
            "timestamp": datetime.utcnow().isoformat(),
            "data": status
        }
        disconnected = []
        for ws in self.active_connections[user_id]:
            try:
                await ws.send_json(message)
            except Exception:
                disconnected.append(ws)
        for ws in disconnected:
            self.disconnect(ws, user_id)

manager = ConnectionManager()

# ============ APP ============

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("WinPulse backend starting...")
    init_db()
    yield
    logger.info("WinPulse backend shutting down...")

app = FastAPI(title="WinPulse API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============ HEALTH ============

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "WinPulse", "version": "1.0.0"}

@app.get("/")
async def root():
    return {"message": "WinPulse API", "docs": "/docs"}

# ============ ANOMALY ROUTES ============

@app.get("/api/anomalies", response_model=List[AnomalyResponse])
async def get_anomalies(
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    severity: Optional[str] = Query(None),
    hours: int = Query(24, ge=1, le=720),
    user_id: int = Depends(get_current_user_id)
):
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    query = db.query(Anomaly).filter(
        and_(Anomaly.user_id == user_id, Anomaly.timestamp >= cutoff)
    )
    if severity:
        query = query.filter(Anomaly.severity == severity)
    return query.order_by(desc(Anomaly.timestamp)).offset(skip).limit(limit).all()

@app.get("/api/anomalies/stats/summary")
async def get_anomaly_stats(
    db: Session = Depends(get_db),
    hours: int = Query(24),
    user_id: int = Depends(get_current_user_id)
):
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    anomalies = db.query(Anomaly).filter(
        and_(Anomaly.user_id == user_id, Anomaly.timestamp >= cutoff)
    ).all()
    total = len(anomalies)
    high = len([a for a in anomalies if a.severity == "high"])
    medium = len([a for a in anomalies if a.severity == "medium"])
    low = len([a for a in anomalies if a.severity == "low"])
    return {
        "total_anomalies": total,
        "high_severity": high,
        "medium_severity": medium,
        "low_severity": low,
        "anomaly_rate": round(total / hours, 2),
        "avg_confidence": round(sum(a.confidence for a in anomalies) / total, 2) if total else 0,
        "avg_z_score": round(sum(abs(a.z_score) for a in anomalies) / total, 2) if total else 0
    }

@app.get("/api/anomalies/{anomaly_id}", response_model=AnomalyResponse)
async def get_anomaly(anomaly_id: int, db: Session = Depends(get_db)):
    anomaly = db.query(Anomaly).filter(Anomaly.id == anomaly_id).first()
    if not anomaly:
        raise HTTPException(status_code=404, detail="Anomaly not found")
    return anomaly

# ============ CORRELATED ANOMALIES ROUTES ============

@app.get("/api/correlated-anomalies", response_model=List[CorrelatedAnomalyResponse])
async def get_correlated_anomalies(
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    hours: int = Query(24, ge=1, le=720),
    user_id: int = Depends(get_current_user_id)
):
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    query = db.query(CorrelatedAnomaly).filter(
        and_(CorrelatedAnomaly.user_id == user_id, CorrelatedAnomaly.timestamp >= cutoff)
    )
    return query.order_by(desc(CorrelatedAnomaly.timestamp)).offset(skip).limit(limit).all()

@app.get("/api/correlated-anomalies/{correlated_id}", response_model=CorrelatedAnomalyResponse)
async def get_correlated_anomaly(
    correlated_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    correlated = db.query(CorrelatedAnomaly).filter(
        and_(CorrelatedAnomaly.id == correlated_id, CorrelatedAnomaly.user_id == user_id)
    ).first()
    if not correlated:
        raise HTTPException(status_code=404, detail="Correlated anomaly not found")
    return correlated

@app.get("/api/correlated-anomalies/stats/summary")
async def get_correlated_anomaly_stats(
    db: Session = Depends(get_db),
    hours: int = Query(24),
    user_id: int = Depends(get_current_user_id)
):
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    correlated = db.query(CorrelatedAnomaly).filter(
        and_(CorrelatedAnomaly.user_id == user_id, CorrelatedAnomaly.timestamp >= cutoff)
    ).all()
    total = len(correlated)
    avg_correlation = round(sum(c.correlation_score for c in correlated) / total, 2) if total else 0
    avg_anomaly_count = round(sum(c.anomaly_count for c in correlated) / total, 2) if total else 0
    return {
        "total_correlated_events": total,
        "avg_correlation_score": avg_correlation,
        "avg_anomalies_per_event": avg_anomaly_count,
        "unique_agents": len(set(agent for c in correlated for agent in c.agents_involved))
    }

# ============ METRICS ROUTES ============

@app.get("/api/metrics/timeseries")
async def get_metric_timeseries(
    metric: str = Query(...),
    agent: str = Query(...),
    db: Session = Depends(get_db),
    hours: int = Query(24, ge=1, le=720),
    user_id: int = Depends(get_current_user_id)
):
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    events = db.query(Event).filter(
        and_(
            Event.user_id == user_id,
            Event.metric == metric,
            Event.agent == agent,
            Event.timestamp >= cutoff
        )
    ).order_by(Event.timestamp).all()
    return {
        "metric": metric,
        "agent": agent,
        "data_points": [{"timestamp": e.timestamp, "value": e.value} for e in events],
        "count": len(events)
    }

@app.get("/api/metrics/latest")
async def get_latest_metrics(
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    events = db.query(Event).filter(
        Event.user_id == user_id
    ).order_by(desc(Event.timestamp)).limit(100).all()
    seen = set()
    results = []
    for e in events:
        key = (e.agent, e.metric)
        if key not in seen:
            seen.add(key)
            results.append({
                "metric": e.metric,
                "agent": e.agent,
                "value": e.value,
                "timestamp": e.timestamp
            })
    return results

# ============ SYSTEM ROUTES ============

@app.get("/api/system/status")
async def get_system_status(
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    return _get_system_status(db, user_id)

@app.get("/api/system/agents")
async def get_agent_status(
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    return _get_agent_status(db, user_id)

@app.get("/api/system/warmup")
async def get_warmup_progress(
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    return _get_warmup_progress(db, user_id)

@app.get("/api/system/overview")
async def get_dashboard_overview(
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    cutoff = datetime.utcnow() - timedelta(hours=24)
    recent = db.query(Anomaly).filter(
        and_(Anomaly.user_id == user_id, Anomaly.timestamp >= cutoff)
    ).order_by(desc(Anomaly.timestamp)).limit(5).all()
    return {
        "system_status": _get_system_status(db, user_id),
        "agents": _get_agent_status(db, user_id),
        "warmup_progress": _get_warmup_progress(db, user_id),
        "recent_anomalies": [
            {"id": a.id, "metric": a.metric, "severity": a.severity, "timestamp": a.timestamp}
            for a in recent
        ]
    }

# ============ WEBSOCKET ============

@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: int):
    await manager.connect(websocket, user_id)
    try:
        # Start a background task to send periodic status updates
        async def send_periodic_status():
            while True:
                try:
                    await asyncio.sleep(30)  # Send status every 30 seconds
                    status = {
                        "type": "status",
                        "timestamp": datetime.utcnow().isoformat(),
                        "user_id": user_id,
                        "message": "System running"
                    }
                    await manager.broadcast_status(user_id, status)
                except Exception as e:
                    logger.error(f"Error sending periodic status: {e}")
                    break

        # Create task for periodic updates
        status_task = asyncio.create_task(send_periodic_status())

        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
            elif data == "status":
                # On-demand status request
                status = {
                    "type": "status",
                    "timestamp": datetime.utcnow().isoformat(),
                    "user_id": user_id,
                    "message": "System running"
                }
                await websocket.send_json(status)
    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id)
        logger.info(f"User {user_id} disconnected from WebSocket")
    except Exception as e:
        logger.error(f"WebSocket error for user {user_id}: {e}")
        manager.disconnect(websocket, user_id)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)