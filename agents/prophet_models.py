"""
Prophet Models Module
- Trains Prophet time-series models per metric
- Makes predictions for expected values
- Handles seasonal patterns and trends
"""

from prophet import Prophet
import pandas as pd
from datetime import datetime, timedelta
import logging
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ProphetModels:
    def __init__(self, user_id: str = "default", db_connection=None):
        """
        Initialize Prophet models for a user.
        
        Args:
            user_id: Username or user identifier (default: "default")
            db_connection: PostgreSQL connection object (optional)
        """
        self.user_id = user_id
        self.db = db_connection
        self.models = {}  # Cache of trained Prophet models
        self.metric_history = {}  # In-memory history for metrics
    
    # Fetch historical data for a metric
    def get_historical_data(self, metric_name: str, days: int = 7) -> pd.DataFrame:
        """
        Fetch historical data points for a metric from the database or memory.
        
        Args:
            metric_name: Name of the metric
            days: Number of days of history to fetch
        
        Returns:
            DataFrame with 'ds' (timestamp) and 'y' (value) columns
        """
        try:
            # Try to fetch from database if available
            if self.db:
                cutoff = datetime.utcnow() - timedelta(days=days)
                query = """
                    SELECT timestamp, value FROM events
                    WHERE user_id = %s AND metric = %s AND timestamp > %s
                    ORDER BY timestamp ASC
                """
                result = self.db.execute(query, (self.user_id, metric_name, cutoff))
                
                data = []
                for row in result:
                    data.append({"ds": row[0], "y": row[1]})
                
                df = pd.DataFrame(data)
                logger.info(f"Fetched {len(df)} data points for {metric_name} from database")
                return df
            
            # Fall back to in-memory history
            if metric_name in self.metric_history:
                data = self.metric_history[metric_name]
                df = pd.DataFrame(data)
                logger.info(f"Using {len(df)} in-memory data points for {metric_name}")
                return df
            
            logger.debug(f"No historical data available for {metric_name}")
            return pd.DataFrame()
        except Exception as e:
            logger.error(f"Error fetching historical data: {e}")
            return pd.DataFrame()
    
    # Train a Prophet model for a metric
    def train_model(self, metric_name: str) -> bool:
        """
        Train a Prophet model on historical data for a metric.
        
        Args:
            metric_name: Name of the metric
        
        Returns:
            True if training succeeded, False otherwise
        """
        try:
            # Get historical data
            df = self.get_historical_data(metric_name)
            
            if len(df) < 100:  # Need minimum data points
                logger.debug(f"Not enough data to train model for {metric_name}")
                return False
            
            # Create and train Prophet model
            model = Prophet(
                yearly_seasonality=False,
                weekly_seasonality=True,
                daily_seasonality=True,
                interval_width=0.95  # 95% confidence interval
            )
            model.fit(df)
            
            # Store model
            self.models[metric_name] = model
            logger.info(f"Trained Prophet model for {metric_name}")
            return True
        except Exception as e:
            logger.error(f"Error training model for {metric_name}: {e}")
            return False
    
    # Make prediction for a metric
    def predict(self, metric_name: str, periods: int = 1) -> pd.DataFrame:
        """
        Make predictions for future values of a metric.
        
        Args:
            metric_name: Name of the metric
            periods: Number of periods to predict ahead
        
        Returns:
            DataFrame with predictions and confidence intervals
        """
        try:
            if metric_name not in self.models:
                # Train model if not already trained
                if not self.train_model(metric_name):
                    return None
            
            model = self.models[metric_name]
            future = model.make_future_dataframe(periods=periods, freq='5S')  # 5-second intervals
            forecast = model.predict(future)
            
            # Return only the forecast columns we need
            return forecast[['ds', 'yhat', 'yhat_lower', 'yhat_upper']].tail(periods)
        except Exception as e:
            logger.error(f"Error making prediction for {metric_name}: {e}")
            return None
    
    # Get expected value and confidence interval
    def get_expected_value(self, metric_name: str) -> dict:
        """
        Get the expected value and confidence bounds for a metric.
        
        Args:
            metric_name: Name of the metric
        
        Returns:
            Dictionary with expected_value, lower_bound, upper_bound
        """
        forecast = self.predict(metric_name, periods=1)
        
        if forecast is None or len(forecast) == 0:
            return None
        
        row = forecast.iloc[0]
        return {
            "expected_value": row['yhat'],
            "lower_bound": row['yhat_lower'],
            "upper_bound": row['yhat_upper']
        }
    
    # Retrain all models (run daily)
    def retrain_all_models(self, metric_names: list) -> int:
        """
        Retrain all Prophet models. Should be called daily.
        
        Args:
            metric_names: List of metric names to retrain
        
        Returns:
            Number of models successfully trained
        """
        trained_count = 0
        for metric_name in metric_names:
            if self.train_model(metric_name):
                trained_count += 1
        
        logger.info(f"Retrained {trained_count}/{len(metric_names)} models")
        return trained_count
