"""
Behavioral Baseline Module
- Stores statistical profile per metric per user
- Tracks mean, std dev, min, max values
- Used as reference for anomaly detection
"""

import json
from datetime import datetime
from typing import Dict, Any
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BehavioralBaseline:
    def __init__(self, user_id: str = "default", db_connection=None):
        """
        Initialize baseline for a specific user.
        
        Args:
            user_id: Username or user identifier (default: "default")
            db_connection: PostgreSQL connection object (optional)
        """
        self.user_id = user_id
        self.db = db_connection
        self.metrics = {}  # In-memory cache of baseline stats
        
        # Load baseline from database if available
        if self.db:
            self.load_baseline()
    
    # Load baseline from database
    def load_baseline(self):
        """Fetch stored baseline stats from PostgreSQL"""
        if not self.db:
            logger.info("Database not available - skipping baseline load")
            return
        
        try:
            query = "SELECT metric_name, stats FROM baseline WHERE user_id = %s"
            result = self.db.execute(query, (self.user_id,))
            
            for row in result:
                metric_name = row[0]
                stats = json.loads(row[1])
                self.metrics[metric_name] = stats
            
            logger.info(f"Loaded baseline for user {self.user_id}: {len(self.metrics)} metrics")
        except Exception as e:
            logger.error(f"Error loading baseline: {e}")
    
    # Save baseline to database
    def save_baseline(self):
        """Store baseline stats to PostgreSQL"""
        if not self.db:
            logger.debug("Database not available - skipping baseline save")
            return
        
        try:
            for metric_name, stats in self.metrics.items():
                query = """
                    INSERT INTO baseline (user_id, metric_name, stats, updated_at)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (user_id, metric_name) DO UPDATE SET stats = %s, updated_at = %s
                """
                stats_json = json.dumps(stats)
                self.db.execute(query, (
                    self.user_id, metric_name, stats_json, datetime.utcnow(),
                    stats_json, datetime.utcnow()
                ))
            logger.info(f"Saved baseline for user {self.user_id}")
        except Exception as e:
            logger.error(f"Error saving baseline: {e}")
    
    # Update baseline with new data point
    def update_metric(self, metric_name: str, value: float):
        """
        Update baseline stats for a metric with a new value.
        Recalculates mean, std dev, min, max.
        
        Args:
            metric_name: Name of the metric (e.g., 'cpu_percent')
            value: New data point
        """
        if metric_name not in self.metrics:
            self.metrics[metric_name] = {
                "mean": value,
                "std_dev": 0,
                "min": value,
                "max": value,
                "count": 1,
                "sum": value,
                "sum_sq": value ** 2
            }
        else:
            stats = self.metrics[metric_name]
            stats["count"] += 1
            stats["sum"] += value
            stats["sum_sq"] += value ** 2
            stats["min"] = min(stats["min"], value)
            stats["max"] = max(stats["max"], value)
            
            # Recalculate mean and std dev
            stats["mean"] = stats["sum"] / stats["count"]
            variance = (stats["sum_sq"] / stats["count"]) - (stats["mean"] ** 2)
            stats["std_dev"] = variance ** 0.5
    
    # Get baseline stats for a metric
    def get_metric_stats(self, metric_name: str) -> Dict[str, Any]:
        """
        Retrieve baseline stats for a specific metric.
        
        Args:
            metric_name: Name of the metric
        
        Returns:
            Dictionary with mean, std_dev, min, max
        """
        if metric_name in self.metrics:
            return self.metrics[metric_name]
        return None
    
    # Check if we have enough data (7-day warmup)
    def is_warmup_complete(self) -> bool:
        """
        Check if baseline has enough data points (7 days of data).
        Anomaly detection only works after warmup.
        
        Returns:
            True if we have sufficient data, False otherwise
        """
        if not self.metrics:
            return False
        
        # Assume 1 data point per 5 seconds = 17,280 points per day
        # 7 days = 120,960 points minimum
        avg_count = sum(m["count"] for m in self.metrics.values()) / len(self.metrics)
        return avg_count >= 120960
    
    # Get all metrics
    def get_all_metrics(self) -> Dict[str, Dict]:
        """Return all baseline metrics"""
        return self.metrics
