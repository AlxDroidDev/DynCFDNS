#!/usr/bin/env python3

import os
import sys
import json
from datetime import datetime, timedelta
from globals import UPDATE_INTERVAL

HEALTH_FILE = "/tmp/dyncfdns_health.json"


def write_health_status():
    """Write current timestamp to health file."""
    try:
        health_data = {
            'last_update': datetime.now().isoformat(),
            'status': 'running'
        }
        with open(HEALTH_FILE, 'w') as f:
            json.dump(health_data, f)
        return True
    except Exception:
        return False

def check_health():
    """Check if the main process is healthy based on heartbeat file."""
    try:
        if not os.path.exists(HEALTH_FILE):
            return False

        with open(HEALTH_FILE, 'r') as f:
            health_data = json.load(f)

        last_update = datetime.fromisoformat(health_data['last_update'])
        current_time = datetime.now()

        if current_time - last_update > timedelta(seconds=UPDATE_INTERVAL+10): # Allow a 10-second grace period
            return False

        return True

    except Exception:
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