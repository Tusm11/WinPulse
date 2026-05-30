"""
Device Monitoring Agent
- Detects USB device connections/disconnections
- Tracks connected devices
- Flags suspicious device activity
"""

import psutil
import redis
import json
from datetime import datetime
import logging
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DeviceAgent:
    def __init__(self, redis_host="localhost", redis_port=6379):
        self.redis_client = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)
        self.previous_partitions = set()
        self.stream_name = "device_events"
    
    # Get all mounted disk partitions
    def get_mounted_devices(self):
        try:
            partitions = psutil.disk_partitions()
            devices = []
            for partition in partitions:
                device_info = {
                    "device": partition.device,
                    "mountpoint": partition.mountpoint,
                    "fstype": partition.fstype,
                    "opts": partition.opts
                }
                devices.append(device_info)
            return devices
        except Exception as e:
            logger.error(f"Error getting devices: {e}")
            return []
    
     # Detect new USB mounts and unmounts
    def detect_device_changes(self, current_devices):
        current_set = {d['device'] for d in current_devices}
        new_devices = current_set - self.previous_partitions
        removed_devices = self.previous_partitions - current_set
        self.previous_partitions = current_set
        return {"new_devices": list(new_devices), "removed_devices": list(removed_devices)}
    
    # Send event to Redis List
    def emit_event(self, metric_name, value, metadata=None):
        event = {
            "timestamp": datetime.utcnow().isoformat(),
            "agent": "device",
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
    
    # Main loop: check devices every 10 seconds
    def run(self):
        logger.info("Device Agent started")
        try:
            while True:
                devices = self.get_mounted_devices()
                changes = self.detect_device_changes(devices)
                
                self.emit_event("total_devices", len(devices))
                
                if changes["new_devices"]:
                    for device in changes["new_devices"]:
                        self.emit_event("device_mounted", 1, {"device": device})
                
                if changes["removed_devices"]:
                    for device in changes["removed_devices"]:
                        self.emit_event("device_unmounted", 1, {"device": device})
                
                time.sleep(10)
        except KeyboardInterrupt:
            logger.info("Device Agent stopped")

if __name__ == "__main__":
    agent = DeviceAgent()
    agent.run()
    