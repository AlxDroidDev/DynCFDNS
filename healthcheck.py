#!/usr/bin/env python3

import os
import sys
import json
from datetime import datetime, timedelta, timezone
from globals import UPDATE_INTERVAL
import tempfile

HEALTH_FILE: str = "dyncfdns_health.json"
HEALTH_FILE_FULL_PATH: str = os.path.join(tempfile.gettempdir(), HEALTH_FILE)

def write_health_status(last_check: datetime = datetime.now(timezone.utc)) -> bool:
    """Write current timestamp to health file."""
    try:
        health_data = {
            'last_check': last_check.isoformat(),
            'status': 'running'
        }
        with open(HEALTH_FILE_FULL_PATH, 'w') as f:
            json.dump(health_data, f)
        return True
    except Exception as e:
        sys.stderr.write(f"Failed to write health status to file:\n{e}")
        return False

def check_health():
    """Check if the main process is healthy based on heartbeat file."""
    try:
        if not os.path.exists(HEALTH_FILE_FULL_PATH):
            return False

        with open(HEALTH_FILE_FULL_PATH, 'r') as f:
            health_data = json.load(f)

        last_check = datetime.fromisoformat(health_data['last_check'])
        current_time = datetime.now(timezone.utc)

        if current_time - last_check > timedelta(seconds=UPDATE_INTERVAL+15): # Allow a 15-second grace period
            return False

        return True

    except Exception as e:
        sys.stderr.write(f"Failed to write health status to file:\n{e}")
        return False


def is_running_in_docker():
    """Detect if running inside a Docker container."""
    # Check for Docker-specific environment variables
    if os.getenv('DOCKER_CONTAINER') or os.getenv('CONTAINER'):
        return True

    # Check for .dockerenv file (created by Docker)
    if os.path.exists('/.dockerenv'):
        return True

    # Check cgroup for docker (most reliable method)
    try:
        with open('/proc/1/cgroup', 'r') as f:
            content = f.read()
            return 'docker' in content or 'containerd' in content
    except (FileNotFoundError, PermissionError):
        pass

    return False


def main():
    """Main health check function for Docker."""
    if check_health():
        sys.exit(0)  # Healthy - Docker expects 0
    else:
        sys.exit(1)  # Unhealthy - Docker expects non-zero

if __name__ == "__main__":
    main()