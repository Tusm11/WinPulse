"""
Anomaly Scoring Module
- Uses p-values for statistical significance testing
- Compares actual values against Prophet predictions
- Classifies anomalies based on probability theory
"""

import logging
from typing import Dict, Any
from datetime import datetime
from scipy import stats
import numpy as np

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AnomalyScorer:
    def __init__(self, prophet_models, baseline):
        """
        Initialize anomaly scorer with statistical methods.
        
        Args:
            prophet_models: ProphetModels instance for predictions
            baseline: BehavioralBaseline instance for stats
        """
        self.prophet = prophet_models
        self.baseline = baseline
        self.p_value_threshold_high = 0.05      # p < 0.05 = high severity
        self.p_value_threshold_medium = 0.10    # p < 0.10 = medium severity
    
    # Calculate z-score (standardized deviation)
    def calculate_z_score(self, metric_name: str, actual_value: float) -> float:
        """
        Calculate z-score: standardized deviation from expected value.
        
        Formula: z = (actual - expected) / std_dev
        
        Args:
            metric_name: Name of the metric
            actual_value: The observed value
        
        Returns:
            Z-score (higher absolute value = more anomalous)
        """
        try:
            # Get expected value from Prophet
            forecast = self.prophet.get_expected_value(metric_name)
            if not forecast:
                return 0.0
            
            expected = forecast["expected_value"]
            
            # Get std dev from baseline
            stats_data = self.baseline.get_metric_stats(metric_name)
            if not stats_data or stats_data["std_dev"] == 0:
                return 0.0
            
            std_dev = stats_data["std_dev"]
            
            # Calculate z-score
            z_score = (actual_value - expected) / std_dev
            return z_score
        except Exception as e:
            logger.error(f"Error calculating z-score for {metric_name}: {e}")
            return 0.0
    
    # Calculate p-value (probability of observing this value under normal conditions)
    def calculate_p_value(self, metric_name: str, actual_value: float) -> float:
        """
        Calculate two-tailed p-value: probability of seeing this value by chance.
        
        Lower p-value = more anomalous (less likely to occur normally)
        
        Args:
            metric_name: Name of the metric
            actual_value: The observed value
        
        Returns:
            P-value (0-1, where 0 = definitely anomalous, 1 = definitely normal)
        """
        try:
            z_score = self.calculate_z_score(metric_name, actual_value)
            
            # Two-tailed p-value: probability of seeing |z| or more extreme
            # stats.norm.cdf(z) gives cumulative probability up to z
            # 1 - cdf(|z|) gives probability beyond |z|
            # Multiply by 2 for two-tailed test
            p_value = 2 * (1 - stats.norm.cdf(abs(z_score)))
            
            return p_value
        except Exception as e:
            logger.error(f"Error calculating p-value for {metric_name}: {e}")
            return 1.0  # Default to normal if error
    
    # Check if value is statistically anomalous
    def is_anomaly(self, metric_name: str, actual_value: float) -> bool:
        """
        Check if a value is statistically anomalous (p < 0.05).
        
        Args:
            metric_name: Name of the metric
            actual_value: The observed value
        
        Returns:
            True if p-value < 0.05, False otherwise
        """
        p_value = self.calculate_p_value(metric_name, actual_value)
        return p_value < self.p_value_threshold_high
    
    # Classify severity based on p-value
    def classify_severity(self, p_value: float) -> str:
        """
        Classify anomaly severity based on statistical significance.
        
        p < 0.05 = high (99.95% confidence it's anomalous)
        p < 0.10 = medium (99% confidence it's anomalous)
        p >= 0.10 = low (not statistically significant)
        
        Args:
            p_value: P-value from 0-1
        
        Returns:
            Severity level: 'low', 'medium', or 'high'
        """
        if p_value < self.p_value_threshold_high:
            return "high"
        elif p_value < self.p_value_threshold_medium:
            return "medium"
        else:
            return "low"
    
    # Calculate confidence level (inverse of p-value)
    def calculate_confidence(self, p_value: float) -> float:
        """
        Convert p-value to confidence percentage.
        
        Confidence = (1 - p_value) * 100
        
        Args:
            p_value: P-value from 0-1
        
        Returns:
            Confidence percentage (0-100)
        """
        return (1 - p_value) * 100
    
    # Create detailed anomaly report
    def create_anomaly_report(self, metric_name: str, actual_value: float, 
                             metadata: Dict = None) -> Dict[str, Any]:
        """
        Create a detailed statistical anomaly report.
        
        Args:
            metric_name: Name of the metric
            actual_value: The observed value
            metadata: Additional context (e.g., process name, IP)
        
        Returns:
            Dictionary with anomaly details and statistical measures
        """
        z_score = self.calculate_z_score(metric_name, actual_value)
        p_value = self.calculate_p_value(metric_name, actual_value)
        severity = self.classify_severity(p_value)
        confidence = self.calculate_confidence(p_value)
        
        forecast = self.prophet.get_expected_value(metric_name)
        expected = forecast["expected_value"] if forecast else None
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "metric": metric_name,
            "actual_value": actual_value,
            "expected_value": expected,
            "z_score": round(z_score, 3),
            "p_value": round(p_value, 6),
            "confidence": round(confidence, 2),  # % confidence it's anomalous
            "severity": severity,
            "is_anomaly": self.is_anomaly(metric_name, actual_value),
            "metadata": metadata or {}
        }
    
    # Batch score multiple metrics
    def score_batch(self, events: list) -> list:
        """
        Score multiple events at once.
        
        Args:
            events: List of dicts with 'metric' and 'value' keys
        
        Returns:
            List of anomaly reports
        """
        reports = []
        for event in events:
            report = self.create_anomaly_report(
                event["metric"],
                event["value"],
                event.get("metadata")
            )
            reports.append(report)
        
        return reports
    
    # Get anomaly statistics
    def get_anomaly_stats(self, reports: list) -> Dict[str, Any]:
        """
        Aggregate statistics from multiple anomaly reports.
        
        Args:
            reports: List of anomaly reports
        
        Returns:
            Dictionary with aggregated stats
        """
        if not reports:
            return {}
        
        anomalies = [r for r in reports if r["is_anomaly"]]
        high_severity = [r for r in anomalies if r["severity"] == "high"]
        
        return {
            "total_events": len(reports),
            "total_anomalies": len(anomalies),
            "anomaly_rate": len(anomalies) / len(reports) if reports else 0,
            "high_severity_count": len(high_severity),
            "avg_confidence": np.mean([r["confidence"] for r in anomalies]) if anomalies else 0,
            "avg_z_score": np.mean([abs(r["z_score"]) for r in anomalies]) if anomalies else 0
        }
