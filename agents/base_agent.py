"""
Base Agent Class
Common functionality for all monitoring agents to reduce boilerplate code.
Each specific agent only needs to implement its unique data collection logic.
"""

import redis
import logging
import json
from datetime import datetime
import time
from abc import ABC, abstractmethod


class BaseAgent(ABC):
    """
    Abstract base class for all monitoring agents.

    Provides:
    - Redis connection management
    - Standardized event emission
    - Logging configuration
    - Main execution loop
    - Error handling

    Subclasses must implement:
    - collect_and_emit(): Collect metrics and emit events
    - get_interval(): Return sleep interval between collections
    """

    def __init__(self, redis_host="localhost", redis_port=6379, stream_name="events"):
        """
        Initialize the base agent.

        Args:
            redis_host: Redis server hostname
            redis_port: Redis server port
            stream_name: Redis Stream name for this agent's events
        """
        self.redis_client = redis.Redis(
            host=redis_host,
            port=redis_port,
            decode_responses=True
        )
        self.stream_name = stream_name
        self.logger = logging.getLogger(self.__class__.__name__)

        # Configure logging if not already configured
        if not self.logger.handlers:
            logging.basicConfig(
                level=logging.INFO,
                format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )

    def emit_event(self, metric_name, value, metadata=None):
        """
        Send an event to Redis List for processing by the orchestrator.

        Args:
            metric_name: Name of the metric (e.g., 'cpu_percent')
            value: The metric value
            metadata: Additional context (e.g., process name, IP)
        """
        event = {
            "timestamp": datetime.utcnow().isoformat(),
            "agent": self.__class__.__name__.lower().replace("agent", ""),
            "metric": metric_name,
            "value": str(value),
            "metadata": json.dumps(metadata or {})
        }

        try:
            # Use Redis List (LPUSH) instead of Streams (XADD) for compatibility
            self.redis_client.lpush(self.stream_name, json.dumps(event))
            self.logger.debug(f"Emitted event: {metric_name} = {value}")
        except Exception as e:
            self.logger.error(f"Failed to emit event: {e}")

    @abstractmethod
    def collect_and_emit(self):
        """
        Collect metrics and emit events.
        Must be implemented by each specific agent.
        """
        pass

    @abstractmethod
    def get_interval(self):
        """
        Return sleep interval in seconds between collections.
        Must be implemented by each specific agent.
        """
        pass

    def run(self):
        """
        Main loop: continuously collect metrics and emit events.
        Runs indefinitely until interrupted.
        """
        self.logger.info(f"{self.__class__.__name__} started")

        try:
            while True:
                start_time = time.time()

                # Collect and emit metrics
                self.collect_and_emit()

                # Calculate sleep time to maintain consistent interval
                elapsed = time.time() - start_time
                sleep_time = max(0, self.get_interval() - elapsed)

                if sleep_time > 0:
                    time.sleep(sleep_time)

        except KeyboardInterrupt:
            self.logger.info(f"{self.__class__.__name__} stopped")
        except Exception as e:
            self.logger.error(f"Unexpected error in {self.__class__.__name__}: {e}")
            raise