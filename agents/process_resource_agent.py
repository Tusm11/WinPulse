"""
Process & Resource Monitoring Agent

PURPOSE:
This agent continuously monitors system processes and resource usage (CPU, RAM, disk I/O, battery).
It tracks which applications are running, their resource consumption, and detects anomalies like
unexpected process spawns, crashes, or unusual resource spikes.

WHAT IT DOES:
- Collects CPU%, RAM%, disk I/O metrics
- Tracks running processes and their resource usage
- Detects new process spawns
- Monitors application crashes
- Sends events to Redis Streams for anomaly detection
"""

import psutil
from typing import Dict, List, Any
from agents.base_agent import BaseAgent


class ProcessResourceAgent(BaseAgent):
    """
    Monitors system processes and resource metrics.

    Attributes:
        redis_client: Connection to Redis for event streaming
        previous_processes: Tracks processes from last scan to detect new spawns/crashes
    """

    def __init__(self, redis_host: str = "localhost", redis_port: int = 6379):
        """
        Initialize the agent with Redis connection.

        Args:
            redis_host: Redis server hostname
            redis_port: Redis server port
        """
        super().__init__(
            redis_host=redis_host,
            redis_port=redis_port,
            stream_name="process_resource_events"
        )
        self.previous_processes = set()

    def collect_cpu_metrics(self) -> Dict[str, Any]:
        """
        Collect CPU usage metrics.

        Returns:
            Dictionary with CPU percentage and per-core breakdown
        """
        return {
            "cpu_percent": psutil.cpu_percent(interval=1),
            "cpu_count": psutil.cpu_count(),
            "cpu_per_core": psutil.cpu_percent(interval=1, percpu=True)
        }

    def collect_memory_metrics(self) -> Dict[str, Any]:
        """
        Collect RAM usage metrics.

        Returns:
            Dictionary with total, used, available memory and percentage
        """
        memory = psutil.virtual_memory()
        return {
            "memory_total": memory.total,
            "memory_used": memory.used,
            "memory_available": memory.available,
            "memory_percent": memory.percent
        }

    def collect_disk_metrics(self) -> Dict[str, Any]:
        """
        Collect disk I/O and usage metrics.

        Returns:
            Dictionary with disk usage and I/O stats
        """
        disk_usage = psutil.disk_usage('/')
        disk_io = psutil.disk_io_counters()

        return {
            "disk_total": disk_usage.total,
            "disk_used": disk_usage.used,
            "disk_free": disk_usage.free,
            "disk_percent": disk_usage.percent,
            "disk_read_bytes": disk_io.read_bytes,
            "disk_write_bytes": disk_io.write_bytes
        }

    def collect_battery_metrics(self) -> Dict[str, Any]:
        """
        Collect battery status (if available).

        Returns:
            Dictionary with battery percentage and status
        """
        try:
            battery = psutil.sensors_battery()
            if battery:
                return {
                    "battery_percent": battery.percent,
                    "battery_plugged": battery.power_plugged,
                    "battery_time_left": battery.secsleft
                }
        except Exception as e:
            self.logger.warning(f"Could not read battery: {e}")

        return {"battery_percent": None}

    def collect_process_metrics(self) -> List[Dict[str, Any]]:
        """
        Collect metrics for all running processes.

        Returns:
            List of dictionaries with process info (name, PID, CPU%, RAM%)
        """
        processes = []

        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
            try:
                processes.append({
                    "pid": proc.info['pid'],
                    "name": proc.info['name'],
                    "cpu_percent": proc.info['cpu_percent'],
                    "memory_percent": proc.info['memory_percent']
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        return processes

    def detect_process_changes(self, current_processes: List[Dict]) -> Dict[str, List]:
        """
        Detect new process spawns and crashes by comparing with previous scan.

        Args:
            current_processes: List of currently running processes

        Returns:
            Dictionary with 'new_processes' and 'crashed_processes' lists
        """
        current_pids = {p['pid'] for p in current_processes}

        new_processes = current_pids - self.previous_processes
        crashed_processes = self.previous_processes - current_pids

        self.previous_processes = current_pids

        return {
            "new_processes": list(new_processes),
            "crashed_processes": list(crashed_processes)
        }

    def collect_and_emit(self):
        """Collect all metrics and emit events."""
        # Collect all metrics
        cpu_metrics = self.collect_cpu_metrics()
        memory_metrics = self.collect_memory_metrics()
        disk_metrics = self.collect_disk_metrics()
        battery_metrics = self.collect_battery_metrics()
        processes = self.collect_process_metrics()
        process_changes = self.detect_process_changes(processes)

        # Emit CPU event
        self.emit_event("cpu_percent", cpu_metrics["cpu_percent"])

        # Emit memory event
        self.emit_event("memory_percent", memory_metrics["memory_percent"])

        # Emit disk event
        self.emit_event("disk_percent", disk_metrics["disk_percent"])

        # Emit battery event if available
        if battery_metrics["battery_percent"] is not None:
            self.emit_event("battery_percent", battery_metrics["battery_percent"])

        # Emit process change events
        if process_changes["new_processes"]:
            self.emit_event("new_processes", len(process_changes["new_processes"]),
                          {"pids": process_changes["new_processes"]})

        if process_changes["crashed_processes"]:
            self.emit_event("crashed_processes", len(process_changes["crashed_processes"]),
                          {"pids": process_changes["crashed_processes"]})

    def get_interval(self):
        """Return 5 seconds interval between collections."""
        return 5


if __name__ == "__main__":
    agent = ProcessResourceAgent()
    agent.run()