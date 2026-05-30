#!/usr/bin/env python
"""
Unified launcher for all WinPulse components
Run this instead of managing individual processes
"""

import subprocess
import sys
import os
from threading import Thread
import time

# Add the project root to Python path so agents can import each other
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)


def run_process(command, name, cwd=None):
    """Run a process and stream its output with prefix"""
    print(f"Starting {name}...")

    # Use current directory if not specified
    if cwd is None:
        cwd = os.getcwd()

    # Set PYTHONPATH to include project root
    env = os.environ.copy()
    env['PYTHONPATH'] = project_root + os.pathsep + env.get('PYTHONPATH', '')

    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
        bufsize=1,
        cwd=cwd,
        env=env
    )

    for line in process.stdout:
        print(f"[{name}] {line}", end='')


def main():
    """Launch all WinPulse components"""
    print("=" * 50)
    print("WinPulse - Starting all components")
    print("=" * 50)

    processes = [
        # Frontend
        (["python", "serve_frontend.py"], "Frontend Server"),
        
        # Monitoring Agents
        (["python", "agents/process_resource_agent.py"], "Process Resource Agent"),
        (["python", "agents/network_agent.py"], "Network Agent"),
        (["python", "agents/session_agent.py"], "Session Agent"),
        (["python", "agents/application_agent.py"], "Application Agent"),
        (["python", "agents/file_system_agent.py"], "File System Agent"),
        (["python", "agents/device_agent.py"], "Device Agent"),
        (["python", "agents/system_events_agent.py"], "System Events Agent"),
        (["python", "agents/orchestrator.py"], "Orchestrator"),

        # Backend
        (["uvicorn", "backend.app:app", "--reload"], "FastAPI Backend"),
    ]

    threads = []

    # Start all processes
    for cmd, name in processes:
        thread = Thread(target=run_process, args=(cmd, name))
        thread.daemon = True  # Dies when main thread dies
        thread.start()
        threads.append(thread)
        # Small stagger to prevent resource spikes on startup
        time.sleep(0.5)

    print("\n" + "=" * 50)
    print("All components started!")
    print("Press Ctrl+C to stop all processes")
    print("=" * 50)

    try:
        # Keep main thread alive
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n" + "=" * 50)
        print("Shutting down all components...")
        print("=" * 50)
        # Note: Daemon threads will be killed automatically when main exits
        sys.exit(0)


if __name__ == "__main__":
    main()