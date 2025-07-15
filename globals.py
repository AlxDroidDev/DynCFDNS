import os
import logging
from secrets import token_bytes
from base64 import b64encode

__CONFIG_PATH     : str = './config/.config.json'


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

def get_api_token() -> str:
    """Get the API token from environment variable, config file, or generate a new one."""
    # Check if API is disabled
    if API_PORT <= 0:
        return ''

    # Try to get token from environment variable
    token = os.getenv('API_TOKEN', '')
    if token:
        return token

    # Try to get token from config file
    token = load_attribute_from_config('api_token')
    if token:
        return token

    # Generate new token
    random_bytes = token_bytes(32)
    token = b64encode(random_bytes).decode('utf-8')
    save_attribute_to_config('api_token', token)
    print(f"Generated new API token: {token}")

    return token

def save_attribute_to_config(attribute: str, value: str) -> bool:
    """Save an attribute to the config file."""
    import json
    try:
        # Ensure config directory exists
        os.makedirs(os.path.dirname(__CONFIG_PATH), exist_ok=True)

        # Load existing config or create new one
        config = {}
        if os.path.exists(__CONFIG_PATH):
            try:
                with open(__CONFIG_PATH, 'r') as f:
                    config = json.load(f)
            except json.JSONDecodeError:
                config = {}

        # Update config with new attribute
        config[attribute] = value

        # Save config
        with open(__CONFIG_PATH, 'w') as f:
            json.dump(config, f, indent=2)
        return True
    except IOError as e:
        logging.warning(f"Could not save {attribute} to config file: {e}")
        return False

def load_attribute_from_config(attribute: str, default: str='') -> str:
    """Load an attribute from the config file."""
    import json
    try:
        if os.path.exists(__CONFIG_PATH):
            with open(__CONFIG_PATH, 'r') as f:
                config = json.load(f)
                return config.get(attribute, '')
    except (json.JSONDecodeError, IOError) as e:
        logging.warning(f"Could not read {attribute} from config file: {e}")
    return default


API_PORT        : int = get_api_port()
UPDATE_INTERVAL : int = get_update_interval()
API_TOKEN       : str = get_api_token()
NOT_FOUND       : str = 'Not Found'
KEY_PREVIOUS_IP : str = 'previous_ip'

