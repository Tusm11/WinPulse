"""
Application Monitoring Agent
- Tracks active window title
- Measures app focus duration
- Detects app switches
"""
import redis
import json
from datetime import datetime
import logging
import time

# Windows-specific:uses pywin32 to get active window
try:
    import win32gui
    import win32process
    import psutil
except ImportError:
    logger = logging.getLogger(__name__)
    logger.error("pywin32 not installed. Install with: pip install pywin32")

logging.basicConfig(level=logging.INFO)
logger=logging.getLogger(__name__)

class ApplicationAgent:
    def __init__(self, redis_host="localhost", redis_port=6379):
        self.redis_client = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)
        self.previous_window = None
        self.focus_start_time = None
        self.stream_name = "application_events"
    
    # Get currently active window title
    def get_active_window(self):
        try:
            hwnd = win32gui.GetForegroundWindow()
            window_title = win32gui.GetWindowText(hwnd)

            # Get the process name from the handle
            _, pid = win32process.GetWindowThreadProcessId(hwnd)

            try:
                proc = psutil.Process(pid)  # Attempts to create a Process object from the pid to get more details
                process_name = proc.name()  # Gets the executable name of the process (e.g., "code.exe", "chrome.exe")
            except Exception as e:
                logger.warning(f"Could not retrieve process name for pid {pid}: {e}")
                process_name = "Unknown process name. Agent wasn't able to retrieve the exact name of the application."

            return {"window_title": window_title, "process_name": process_name, "pid": pid}
        except Exception as e:
            logger.error(f"Error getting active window: {e}")
            return None

    def calculate_focus_duration(self) -> float:
        """
        Calculate how long the previous window was in focus.
        
        Returns:
            Duration in seconds
        """
        if self.focus_start_time is None:
            return 0.0
        
        duration = (datetime.now() - self.focus_start_time).total_seconds()
        return duration

    def emit_event(self, metric_name, value, metadata=None):
        event = {
            "timestamp": datetime.utcnow().isoformat(),
            "agent": "application",
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
    

    #main loop of the agent: checks active window for every 2 seconds
    def run(self):
        logger.info("Application agent started...")
        try:
            while True:
                current_window=self.get_active_window()
                
                if current_window:
                    #detects window switch
                    if current_window['window_title']!=self.previous_window:
                        #emit focus duration for previous window
                        if self.previous_window:
                            duration = self.calculate_focus_duration()
                            self.emit_event("app_focus_duration", duration, 
                                          {"app": self.previous_window})
                        
                        #emit new window focus to redis stream
                        self.emit_event("windows_focus",1,{
                            "window_title":current_window["window_title"],
                            "process_name":current_window["process_name"]
                        })
                        self.previous_window=current_window["window_title"]
                        self.focus_start_time=datetime.now()
                time.sleep(2)
        except KeyboardInterrupt:
            logger.info("Application Agent stopped!!")

if __name__=="__main__":
    agent=ApplicationAgent()
    agent.run()