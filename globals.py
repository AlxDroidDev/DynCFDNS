import os
import logging


def get_update_interval() -> int:
    """Get the update interval from environment variable or default to 60 seconds."""
    try:
        return max(1, int(os.getenv('UPDATE_INTERVAL', '120')))
    except ValueError:
        logging.warn("Expected UPDATE_INTERVAL to be a valid integer. Using default value of 2 minutes.")
        return 120


UPDATE_INTERVAL: int = get_update_interval()
