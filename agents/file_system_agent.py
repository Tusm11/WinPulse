"""
File System Monitoring Agent
- Watches for file changes in key directories
- Detects new files, deletions, modifications
- Tracks file activity patterns
"""

import redis
import json
import time
from datetime import datetime
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler as WatchdogEventHandler
import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FileSystemEventHandler(WatchdogEventHandler):
    def __init__(self,agent):
        self.agent=agent
    
    #detects new files created
    def on_created(self, event):
        if not event.is_directory:
            self.agent.emit_event("file_created", 1, {"path": event.src_path})
    
    #detects file modifications
    def on_modified(self, event):
        if not event.is_directory:
            self.agent.emit_event("file_modified", 1, {"path": event.src_path})

    #detects file deletions
    def on_deleted(self, event):
        if not event.is_directory:
            self.agent.emit_event("file_deleted", 1, {"path": event.src_path})

class FileSystemAgent:
    def __init__(self,redis_host="localhost",redis_port=6379):
        self.redis_client = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)
        self.stream_name = "filesystem_events"
        self.observer = Observer()

        #directories to monitor
        self.watch_dirs=[
            os.path.expanduser("~\\Documents"),
            os.path.expanduser("~\\Downloads"),
            os.path.expanduser("~\\Desktop"),
            os.path.expanduser("~\\AppData\\Local")
        ]
        #Sends event to Redis List
    def emit_event(self, metric_name, value, metadata=None):
        event = {
            "timestamp": datetime.utcnow().isoformat(),
            "agent": "filesystem",
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

    #starts watching directories
    def run(self):
        logger.info("File System Agent started...")

        # Set up watchers for each directory
        event_handler = FileSystemEventHandler(self)

        for watch_dir in self.watch_dirs:
            if os.path.exists(watch_dir):
                self.observer.schedule(event_handler, watch_dir, recursive=True)
                logger.info(f"Watching: {watch_dir}")
        
        self.observer.start()

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            self.observer.stop()
            logger.info("File System Agent stopped!!")
        
        self.observer.join()

if __name__ == "__main__":
    agent = FileSystemAgent()
    agent.run()