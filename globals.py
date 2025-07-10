import os


def get_update_interval() -> int:
    """Get the update interval from environment variable or default to 60 seconds."""
    try:
        return max(1, int(os.getenv('UPDATE_INTERVAL', '60')))
    except ValueError:
        warn("UPDATE_INTERVAL must be a valid integer. Using default value of 60 minutes.")
        return 60


UPDATE_INTERVAL: int = get_update_interval()
