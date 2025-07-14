import os
import logging


def get_update_interval() -> int:
    """Get the update interval from environment variable or default to 60 seconds."""
    try:
        return max(1, int(os.getenv('UPDATE_INTERVAL', '120')))
    except ValueError:
        logging.warn("Expected UPDATE_INTERVAL to be a valid integer. Using default value of 2 minutes.")
        return 120

def get_api_port() -> int:
    """Get the API port from environment variable or default to 5000."""
    try:
        return max(1, int(os.getenv('API_PORT', '5000')))
    except ValueError:
        logging.warn("Expected API_PORT to be a valid integer. Using default value of 5000.")
        return 5000

API_PORT: int = get_api_port()
UPDATE_INTERVAL: int = get_update_interval()
