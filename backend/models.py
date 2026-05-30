"""
Database Models & Connection
- SQLAlchemy ORM models
- PostgreSQL connection pool
- Session management
"""

from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, JSON, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
from sqlalchemy.exc import OperationalError
from datetime import datetime
import os
import logging
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Validate DATABASE_URL
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:password@localhost:5432/winpulse")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set")
if not DATABASE_URL.startswith(("postgresql://", "postgres://")):
    raise ValueError(f"Invalid DATABASE_URL format: {DATABASE_URL}. Must start with postgresql:// or postgres://")

# Database setup with retry logic
def create_engine_with_retry(url: str, max_retries: int = 3, retry_delay: int = 1):
    """Create engine with retry logic for connection failures"""
    for attempt in range(max_retries):
        try:
            engine = create_engine(url, poolclass=QueuePool, pool_size=10, max_overflow=20, pool_pre_ping=True)
            # Test the connection
            with engine.connect() as conn:
                logger.info("✓ Database connection successful")
            return engine
        except OperationalError as e:
            if attempt < max_retries - 1:
                logger.debug(f"Database connection failed (attempt {attempt + 1}/{max_retries}). Retrying in {retry_delay}s...")
                time.sleep(retry_delay)
            else:
                logger.warning(f"⚠ Database unavailable after {max_retries} attempts. Running in memory-only mode.")
                return None

try:
    engine = create_engine_with_retry(DATABASE_URL, max_retries=3, retry_delay=1)
except Exception as e:
    logger.warning(f"Database initialization skipped: {e}")
    engine = None

if engine:
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
else:
    SessionLocal = None
    
Base = declarative_base()

def get_db() -> Session:
    """Dependency for FastAPI routes"""
    if SessionLocal is None:
        logger.warning("Database not available - returning None")
        return None
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """Initialize database tables"""
    if engine is None:
        logger.warning("Database not available - skipping initialization")
        return
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables initialized successfully")
    except OperationalError as e:
        logger.error(f"Database connection error during initialization: {e}")
    except Exception as e:
        logger.error(f"Error initializing database: {e}")

# Models
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String(255), unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_seen = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)

class Event(Base):
    __tablename__ = "events"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    agent = Column(String(50), nullable=False)
    metric = Column(String(100), nullable=False)
    value = Column(Float, nullable=False)
    event_metadata = Column(JSON, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)

class Baseline(Base):
    __tablename__ = "baseline"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    metric_name = Column(String(100), nullable=False)
    stats = Column(JSON, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Anomaly(Base):
    __tablename__ = "anomalies"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    metric = Column(String(100), nullable=False)
    agent = Column(String(50), nullable=False)
    actual_value = Column(Float, nullable=False)
    expected_value = Column(Float, nullable=True)
    z_score = Column(Float, nullable=False)
    p_value = Column(Float, nullable=False)
    confidence = Column(Float, nullable=False)
    severity = Column(String(20), nullable=False)
    anomaly_metadata = Column(JSON, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)

class CorrelatedAnomaly(Base):
    __tablename__ = "correlated_anomalies"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    anomaly_ids = Column(JSON, nullable=False)
    agents_involved = Column(JSON, nullable=False)
    anomaly_count = Column(Integer, nullable=False)
    correlation_score = Column(Float, nullable=False)
    explanation = Column(String(2000), nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)

class SystemStatus(Base):
    __tablename__ = "system_status"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    warmup_complete = Column(Boolean, default=False)
    total_anomalies = Column(Integer, default=0)
    high_severity_count = Column(Integer, default=0)
    anomaly_rate = Column(Float, default=0.0)
    last_anomaly_timestamp = Column(DateTime, nullable=True)
    agents_active = Column(JSON, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
