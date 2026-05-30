"""
Session monitoring Agent:
- detects login/logout events
- tracks active user and session duration
- builds active hours heatmaps
"""
import psutil
import redis
import logging 
import time
import json
from datetime import datetime

#Initialize logging for this module
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SessionAgent:
    def __init__(self,redis_host="localhost",redis_port=6379):
        self.redis_client=redis.Redis(host=redis_host,port=redis_port,decode_responses=True)
        self.previous_users=set() #used to track previous users seen previously and sets are used to avoid duplicates
        self.stream_name="session_events" # Redis Streams are a data structure for storing sequences of events with timestamps

    #get currently logged-in users
    def get_active_users(self):
        try:
            users = psutil.users()
            return [{"username": u.name, "terminal": u.terminal, "started": u.started} for u in users]
        except Exception as e:
            logger.error(f"Error getting users: {e}")
            return []
    
    #get boot time (system startups)
    def get_boot_time(self):
        try:
            boot_time=datetime.fromtimestamp(psutil.boot_time())
            return boot_time.isoformat()
        except:
            logger.error(f"Error getting boot time: {e}")
            return None
    
    #Detect login/logout events
    def detect_session_changes(self, current_users):
        current_usernames = {u['username'] for u in current_users}
        new_logins = current_usernames - self.previous_users
        logouts = self.previous_users - current_usernames
        self.previous_users = current_usernames
        return {"new_logins": list(new_logins), "logouts": list(logouts)}
    
    #send event to Redis
    def emit_event(self, metric_name, value, metadata=None):
        event = {
            "timestamp": datetime.utcnow().isoformat(),
            "agent": "session",
            "metric": metric_name,
            "value": str(value),
            "metadata": json.dumps(metadata or {})
        }
        try:
            # Use Redis List (LPUSH) instead of Streams (XADD) for compatibility
            self.redis_client.lpush(self.stream_name, json.dumps(event))
            logger.info(f"Emitted: {metric_name}:{value}")
        except Exception as e:
            logger.error(f"Failed to emit the event: {e}")
    
    #main loop: checks session for every 10 seconds
    def run(self):
        logger.info("Session agent started...")
        try:
            while True:
                users = self.get_active_users()
                boot_time = self.get_boot_time()
                changes = self.detect_session_changes(users)

                self.emit_event("active_users", len(users), {"users": [u['username'] for u in users]})

                if boot_time:
                    # Convert boot_time ISO string to timestamp (float)
                    boot_timestamp = datetime.fromisoformat(boot_time).timestamp()
                    self.emit_event("boot_time", boot_timestamp)
                if changes["new_logins"]:
                    for user in changes["new_logins"]:
                        self.emit_event("login", 1, {"username": user})
                if changes["logouts"]:
                    for user in changes["logouts"]:
                        self.emit_event("logout", 1, {"username": user})
                #tracks active hour(0-23):
                current_hour = datetime.now().hour
                self.emit_event("active_hour", current_hour)

                time.sleep(10)
        except KeyboardInterrupt:
            logger.info("Session Agent stopped!!")
if __name__ == "__main__":
    agent = SessionAgent()
    agent.run()