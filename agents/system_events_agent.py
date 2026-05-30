"""
System Events Monitoring Agent
- Reads Windows Event Log
- Detects critical events, service start/stop
- Tracks system crashes and errors
"""

import redis
import json
from datetime import datetime
import logging
import time

# Windows Event Log access
try:
    import win32evtlog
    import win32con
except ImportError:
    logger = logging.getLogger(__name__)
    logger.error("pywin32 not installed. Install with: pip install pywin32")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SystemEventsAgent:
    def __init__(self, redis_host="localhost", redis_port=6379):
        self.redis_client = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)
        self.stream_name = "system_events"
        self.last_event_id = 0  # Track last event ID to avoid re-reading
    
    # Read Windows Event Log
    def get_system_events(self):
        try:
            # Open System event log
            handle = win32evtlog.OpenEventLog(None, "System")
            flags = win32evtlog.EVENTLOG_BACKWARDS_READ | win32evtlog.EVENTLOG_SEQUENTIAL_READ
            
            # Read last 100 events
            events = win32evtlog.ReadEventLog(handle, flags, 0)
            
            critical_events = []
            for event in events:
                try:
                    # PyEventLogRecord has properties, not methods
                    event_id = event.EventID
                    event_type = event.EventType
                    source = event.SourceName
                    message = event.StringInserts
                    
                    # Skip if we've already processed this event
                    if event_id <= self.last_event_id:
                        continue
                    
                    # Filter for critical events (errors and warnings)
                    if event_type in [win32con.EVENTLOG_ERROR_TYPE, win32con.EVENTLOG_WARNING_TYPE]:
                        critical_events.append({
                            "event_id": event_id,
                            "type": "error" if event_type == win32con.EVENTLOG_ERROR_TYPE else "warning",
                            "source": source,
                            "message": message if isinstance(message, str) else str(message)
                        })
                    
                    # Update last_event_id to the highest we've seen
                    self.last_event_id = max(self.last_event_id, event_id)
                except Exception as e:
                    logger.warning(f"Error processing event: {e}")
                    continue
            
            win32evtlog.CloseEventLog(handle)
            return critical_events
        except Exception as e:
            logger.error(f"Error reading event log: {e}")
            return []
    
    # Send event to Redis List
    def emit_event(self, metric_name, value, metadata=None):
        event = {
            "timestamp": datetime.utcnow().isoformat(),
            "agent": "system_events",
            "metric": metric_name,
            "value": str(value),
            "metadata": json.dumps(metadata or {})
        }
        try:
            # Use Redis List (LPUSH) instead of Streams (XADD) for compatibility
            self.redis_client.lpush(self.stream_name, json.dumps(event))
            logger.info(f"Emitted: {metric_name} = {value}")
        except Exception as e:
            logger.error(f"Failed to emit event: {e}")
    
    # Main loop: check system events every 30 seconds
    def run(self):
        logger.info("System Events Agent started")
        try:
            while True:
                events = self.get_system_events()
                
                if events:
                    self.emit_event("critical_events", len(events), {"events": events})
                    
                    # Emit individual event details
                    for evt in events:
                        self.emit_event(f"event_{evt['type']}", 1, {
                            "source": evt['source'],
                            "event_id": evt['event_id']
                        })
                
                time.sleep(30)
        except KeyboardInterrupt:
            logger.info("System Events Agent stopped")

if __name__ == "__main__":
    agent = SystemEventsAgent()
    agent.run()
