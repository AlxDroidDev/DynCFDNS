import logging
import os
import time
from datetime import datetime
from threading import Lock
from typing import Optional, Tuple

import httpx
import tldextract
from cloudflare import Cloudflare

from globals import UPDATE_INTERVAL, NOT_FOUND, KEY_PREVIOUS_IP, load_attribute_from_config, save_attribute_to_config
from healthcheck import write_health_status

logger = logging.getLogger("DynCloudflareDNS")

info = logger.info
warn = logger.warning
error = logger.error

__default_ip: str = '10.0.0.254'  # Default placeholder IP
__previous_ip: str = ''
PREVIOUS_IP_FILENAME: str = 'logs/previous_ip.txt'

__last_check: Optional[datetime] = None
__last_update: Optional[datetime] = None
__updatable_hosts: dict = {}  # Dictionary to hold hosts that can be updated


# Thread-safe lock for shared resources
# This is an important thing: this Lock is necessary because some of these
# global variables are accessed by both the main thread and the API thread.
# The simple correct way to ensure both can access them safely is to use a lock.
thread_safe_lock: Lock = Lock()


def configure_logging():
    # Create logs directory if it doesn't exist
    log_dir = "/app/logs"
    os.makedirs(log_dir, exist_ok=True)

    # Create formatters
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    # Create console handler (stderr)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    # Create file handler
    file_handler = logging.FileHandler("/app/logs/dyncfdns.log")
    file_handler.setFormatter(formatter)

    # Configure root logger
    logging.basicConfig(
        level=logging.INFO,
        handlers=[console_handler, file_handler]
    )


def get_external_ip() -> Optional[str]:
    try:
        response = httpx.get('https://api.ipify.org?format=json', timeout=httpx.Timeout(15.0))
        response.raise_for_status()
        return response.json()['ip']
    except Exception as e:
        error(f"Error fetching external IP: {e}")
        return None


# noinspection PyTypeChecker
def get_record_id_by_name(cf: Cloudflare, zone_id: str, record_name: str) -> Tuple[
    Optional[str], Optional[str], Optional[bool]]:
    try:
        record = cf.dns.records.list(zone_id=zone_id, name=record_name)
        if record:
            if record.result_info.count == 0:
                warn(
                    f"No DNS record found for {record_name} in zone {zone_id}.\nIf the ALLOW_CREATE_HOSTS is set to true, I'll try to create a new record.")
                return NOT_FOUND, None, None
            if record.result_info.count > 1:
                warn(f"Multiple DNS records found for {record_name} in zone {zone_id}. Using the first one.")
            return record.result[0].id, record.result[0].type, record.result[0].proxied
        else:
            return None, None, None
    except Exception as e:
        error(f"An error occurred: {e}")
        return None, None, None


def create_new_host_record(cf: Cloudflare, host: str, domain: str, zone_id: str) -> Optional[str]:
    try:
        record = cf.dns.records.create(
            zone_id=zone_id,
            type='A',
            name=f'{host}',
            content=__previous_ip,  # Placeholder IP, will be updated later
            proxied=False,
            ttl=UPDATE_INTERVAL
        )

        if record:
            info(f"Created new DNS record for {host}.{domain}")
            return record.id
        else:
            error(f"Failed to create DNS record for {host}.{domain}")
            return None
    except Exception as e:
        error(f"Error creating DNS record for {host}.{domain}: {e}")
        return None


def update_cloudflare_dns_record(client: Cloudflare, host_record: dict) -> bool:
    try:
        record = client.dns.records.update(
            dns_record_id=host_record['record_id'],
            zone_id=host_record['zone_id'],
            content=host_record['content'],
            type=host_record['type'],
            name=host_record['name']
        )
        info(f"Updated DNS record for {host_record['name']} to {host_record['content']}")
        return record is not None and getattr(record, 'success', True)
    except Exception as e:
        error(f"Error updating DNS record for {host_record['name']}: {e}")
        return False


def assemble_hosts_records(api_token: str, api_key: str, api_email: str, host_list: list[str],
                           allow_create_hosts: bool = False) -> dict:
    cf = Cloudflare(api_token=api_token, api_email=api_email, api_key=api_key)
    try:
        zones = cf.zones.list()
        if not zones.result:
            error("No zones found in the provided account.")
            return {}
    except Exception as e:
        error(f"Error fetching zones: {e}\nCheck the API credentials and permissions.")
        return {}

    zone_id_map = {zone.name: zone.id for zone in zones.result if zone.name in get_tlds(host_list)}

    if not zone_id_map:
        error("No matching zones found for the provided host list.")
        return {}

    valid_updatable_hosts: dict = {}
    for host in host_list:
        domain = get_domain(host)
        if domain in zone_id_map:
            record_id, record_type, proxied = get_record_id_by_name(cf, zone_id_map[domain], host)
            if (record_id == NOT_FOUND) and allow_create_hosts:
                record_id, record_type, proxied = create_new_host_record(cf, host, domain,
                                                                         zone_id_map[domain]), 'A', False
            if record_id:
                valid_updatable_hosts[host] = {
                    'host': host,
                    'domain': domain,
                    'zone_id': zone_id_map[domain],
                    'record_type': record_type,
                    'record_id': record_id,
                    'proxied': proxied
                }
            else:
                warn(f"No DNS record found for {host} in zone {zone_id_map[domain]}")
        else:
            warn(f"Domain {domain} not found in Cloudflare zones for host {host}")
    return valid_updatable_hosts


def get_domain(fqdn: str) -> str:
    ext = tldextract.extract(fqdn)
    return f"{ext.domain}.{ext.suffix}"


def get_tlds(host_list: list[str]) -> set:
    return {get_domain(host) for host in host_list}


def update_dns_records(api_token: str, api_key: str, api_email: str, actual_update_hosts: dict) -> bool:
    """
    Updates DNS records in Cloudflare if the external IP has changed.

    Args:
        api_token (str): Cloudflare API token for authentication
        api_key (str): Cloudflare API key for authentication
        api_email (str): Email associated with Cloudflare account
        actual_update_hosts (dict): Dictionary containing host records to update with structure:
            {
                'host_name': {
                    'record_id': str,
                    'zone_id': str,
                    'record_type': str,
                    'host': str,
                    'proxied': bool
                }
            }

    Returns:
        bool: True if all records were updated successfully, False otherwise

    Note:
        The function checks if the external IP has changed before attempting any updates.
        If the IP hasn't changed, it returns True without making any API calls.
    """
    global __previous_ip, __last_check, __last_update
    result = False
    external_ip = get_external_ip()
    __last_check = datetime.now()
    if not external_ip:
        error("Could not retrieve external IP address.")
        return result

    if external_ip == __previous_ip:
        info("External IP has not changed, skipping DNS update.")
        return True

    cf = Cloudflare(api_token=api_token, api_email=api_email, api_key=api_key)
    results = []
    for host_info in actual_update_hosts.values():
        host_record = {
            'record_id': host_info['record_id'],
            'zone_id': host_info['zone_id'],
            'type': host_info['record_type'],
            'name': host_info['host'],
            'content': external_ip,
            'proxied': host_info['proxied']
        }
        results.append(update_cloudflare_dns_record(cf, host_record))
    if all(results):
        save_current_ip(external_ip)
        __last_update = datetime.now()
        result = True
    return result


def get_env_var(name: str, default: Optional[str] = None) -> str:
    """Get required environment variable with validation."""
    value = os.getenv(name)
    if not value:
        if default:
            value = default
        else:
            error(f"{name} environment variable is not set.")
            raise EnvironmentError(f"{name} is required")
    return value


def save_current_ip(ip: str):
    """Save current IP as previous a file."""
    global __previous_ip

    if ip != __previous_ip:
        if save_attribute_to_config(KEY_PREVIOUS_IP, ip):
            __previous_ip = ip
            info(f"Previous IP updated to {ip}")
    else:
        info("IP has not changed, no update needed.")


def load_previous_ip() -> str:
    """Load previous IP from file."""
    global __previous_ip, PREVIOUS_IP_FILENAME
    __previous_ip = load_attribute_from_config(KEY_PREVIOUS_IP,  '')
    if not __previous_ip:
        save_current_ip(__default_ip)
    return __previous_ip


def check_ip_file_folder():
    """Ensure the logs directory exists and the previous IP file is created."""
    global PREVIOUS_IP_FILENAME
    log_dir = os.path.dirname(PREVIOUS_IP_FILENAME)
    if not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)
    if not os.path.exists(PREVIOUS_IP_FILENAME):
        with open(PREVIOUS_IP_FILENAME, 'w') as f:
            f.write(__default_ip)
        info(f"Created {PREVIOUS_IP_FILENAME} with default IP {__default_ip}")


def get_updatable_hosts() -> dict:
    """Thread-safe function to retrieve the updatable hosts dictionary.
    Used by the API to provide current host information.
    """
    with thread_safe_lock:
        global __updatable_hosts
        return __updatable_hosts


def get_last_check() -> Optional[datetime]:
    """Thread-safe function to retrieve the last check timestamp.
    Used by the API to provide current health status.
    """
    with thread_safe_lock:
        global __last_check
        return __last_check


def get_last_update() -> Optional[datetime]:
    """Thread-safe function to retrieve the last update timestamp.
    Used by the API to provide current update status.
    """
    with thread_safe_lock:
        global __last_update
        return __last_update


def get_previous_ip() -> str:
    """Thread-safe function to retrieve the last saved IP address.
    Used by the API to provide current IP information.
    """
    with thread_safe_lock:
        global __previous_ip
        return __previous_ip


def main():
    load_previous_ip()
    configure_logging()
    global __updatable_hosts

    try:
        # Validate required environment variables
        api_token = get_env_var('CLOUDFLARE_API_TOKEN')
        api_key = get_env_var('CLOUDFLARE_API_KEY')
        api_email = get_env_var('CLOUDFLARE_API_EMAIL')
        allow_create_hosts = get_env_var('ALLOW_CREATE_HOSTS', 'false').lower() in ['true', '1', 'yes']

        host_list_str = os.getenv('HOST_LIST', '')
        if not host_list_str:
            error("HOST_LIST environment variable is not set.")
            return

        host_list = list({host.strip().lower() for host in host_list_str.split(',') if host.strip()})

    except (ValueError, TypeError) as e:
        error(f"Configuration error: {e}")
        return

    with thread_safe_lock:
        __updatable_hosts = assemble_hosts_records(api_token, api_key, api_email, host_list, allow_create_hosts)

    if not __updatable_hosts:
        error("No valid hosts found to monitor. Exiting.")
        return

    info(f"Starting DNS update service. Will update every {UPDATE_INTERVAL} seconds.")
    with thread_safe_lock:
        info(f"Monitoring hosts: {list(__updatable_hosts.keys())}")

    while True:
        try:
            info(f"Updating DNS records at {time.strftime('%Y-%m-%d %H:%M:%S')}")
            with thread_safe_lock:
                success = update_dns_records(api_token, api_key, api_email, __updatable_hosts)

            if success:
                info("All DNS records updated successfully!")
            else:
                warn("Some DNS record updates failed.")
            with thread_safe_lock:
                write_health_status(__last_check)
            info(f"Next check in {UPDATE_INTERVAL} seconds...")
            time.sleep(UPDATE_INTERVAL)

        except KeyboardInterrupt:
            warn("\nReceived interrupt signal. Shutting down...")
            break
        except Exception as e:
            error(f"Unexpected error during DNS update: {e}")
            info(f"Retrying in {UPDATE_INTERVAL} seconds...")
            time.sleep(UPDATE_INTERVAL)

