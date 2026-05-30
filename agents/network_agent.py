"""
Network Monitoring Agent

PURPOSE:
This agent monitors all network connections on the system. It tracks which processes are
connecting to which IPs/ports, how much data is being transferred, and flags suspicious
connections (e.g., connections to unknown IPs, unusual ports, or high data transfer).

WHAT IT DOES:
- Lists all active network connections per process
- Tracks bytes sent/received per connection
- Identifies outbound IPs and ports
- Detects new connections and connection closures
- Flags suspicious patterns (e.g., connections to rare IPs)
"""

import psutil
import json
from typing import Dict, List, Any, Set
from agents.base_agent import BaseAgent


class NetworkAgent(BaseAgent):
    """
    Monitors network connections and data transfer.

    Attributes:
        redis_client: Connection to Redis for event streaming
        previous_connections: Tracks connections from last scan to detect new/closed connections
        known_ips: Set of IPs the system normally connects to (built over time)
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
            stream_name="network_events"
        )
        self.previous_connections = set()
        self.known_ips = set()

    def get_active_connections(self) -> List[Dict[str, Any]]:
        """
        Get all active network connections on the system.

        Returns:
            List of dictionaries with connection details (process, IP, port, status)
        """
        connections = []

        try:
            for conn in psutil.net_connections(kind='inet'):
                try:
                    # Get process name for this connection
                    proc = psutil.Process(conn.pid)
                    process_name = proc.name()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    process_name = "unknown"

                connection_info = {
                    "pid": conn.pid,
                    "process_name": process_name,
                    "local_ip": conn.laddr.ip if conn.laddr else None,
                    "local_port": conn.laddr.port if conn.laddr else None,
                    "remote_ip": conn.raddr.ip if conn.raddr else None,
                    "remote_port": conn.raddr.port if conn.raddr else None,
                    "status": conn.status,
                    "type": conn.type
                }

                connections.append(connection_info)

        except Exception as e:
            self.logger.error(f"Error getting connections: {e}")

        return connections

    def get_network_io_counters(self) -> Dict[str, Any]:
        """
        Get system-wide network I/O statistics (bytes sent/received).

        Returns:
            Dictionary with total bytes sent/received and packet counts
        """
        try:
            io_counters = psutil.net_io_counters()
            return {
                "bytes_sent": io_counters.bytes_sent,
                "bytes_recv": io_counters.bytes_recv,
                "packets_sent": io_counters.packets_sent,
                "packets_recv": io_counters.packets_recv,
                "errin": io_counters.errin,
                "errout": io_counters.errout,
                "dropin": io_counters.dropin,
                "dropout": io_counters.dropout
            }
        except Exception as e:
            self.logger.error(f"Error getting network I/O counters: {e}")
            return {}

    def detect_connection_changes(self, current_connections: List[Dict]) -> Dict[str, List]:
        """
        Detect new connections and closed connections by comparing with previous scan.

        Args:
            current_connections: List of currently active connections

        Returns:
            Dictionary with 'new_connections' and 'closed_connections' lists
        """
        # Create a hashable representation of each connection
        current_conn_set = {
            (c['pid'], c['remote_ip'], c['remote_port'])
            for c in current_connections
            if c['remote_ip']  # Only track outbound connections
        }

        new_connections = current_conn_set - self.previous_connections
        closed_connections = self.previous_connections - current_conn_set

        self.previous_connections = current_conn_set

        return {
            "new_connections": list(new_connections),
            "closed_connections": list(closed_connections)
        }

    def identify_suspicious_ips(self, connections: List[Dict]) -> List[str]:
        """
        Identify IPs that are not in the known set (potential anomalies).

        Args:
            connections: List of active connections

        Returns:
            List of suspicious (unknown) remote IPs
        """
        suspicious = []

        for conn in connections:
            remote_ip = conn.get('remote_ip')
            if remote_ip and remote_ip not in self.known_ips:
                # Add to known IPs for future reference
                self.known_ips.add(remote_ip)
                suspicious.append(remote_ip)

        return suspicious

    def collect_and_emit(self):
        """Monitor network activity and emit events."""
        # Get current network state
        connections = self.get_active_connections()
        io_counters = self.get_network_io_counters()
        connection_changes = self.detect_connection_changes(connections)
        suspicious_ips = self.identify_suspicious_ips(connections)

        # Emit network I/O events
        if io_counters:
            self.emit_event("bytes_sent", io_counters.get("bytes_sent", 0))
            self.emit_event("bytes_recv", io_counters.get("bytes_recv", 0))

        # Emit connection count event
        self.emit_event("active_connections", len(connections))

        # Emit new connection events
        if connection_changes["new_connections"]:
            for pid, remote_ip, remote_port in connection_changes["new_connections"]:
                self.emit_event("new_connection", 1, {
                    "pid": pid,
                    "remote_ip": remote_ip,
                    "remote_port": remote_port
                })

        # Emit closed connection events
        if connection_changes["closed_connections"]:
            self.emit_event("closed_connections", len(connection_changes["closed_connections"]))

        # Emit suspicious IP events
        if suspicious_ips:
            self.emit_event("unknown_ips", len(suspicious_ips), {
                "ips": suspicious_ips
            })

    def get_interval(self):
        """Return 5 seconds interval between collections."""
        return 5


if __name__ == "__main__":
    agent = NetworkAgent()
    agent.run()