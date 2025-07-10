import json
import logging
import os
import time
from typing import Optional, Dict, List, Tuple
from healthcheck import write_health_status
import requests
import tldextract
from cloudflare import Cloudflare

logger = logging.getLogger("dyn_cloudflare_dns_updater")

info = logger.info
warn = logger.warning
error = logger.error

previous_ip: str = '0.0.0.0'
previous_ip_filename = '/app/logs/previous_ip.txt'

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
        response = requests.get('https://api.ipify.org?format=json', timeout=15)
        response.raise_for_status()
        return response.json()['ip']
    except requests.RequestException as e:
        error(f"Error fetching external IP: {e}")
        return None


def get_record_id_by_name(cf: Cloudflare, zone_id: str, record_name: str) ->  Tuple[Optional[str], Optional[str], Optional[bool]]:
    try:
        record = json.loads(cf.dns.records.list(zone_id=zone_id, name=record_name).model_dump_json())
        if record['result_info']['count'] != 1:
            error(f"Either more than one or No DNS record found for {record_name} in zone {zone_id}")
            return None, None, None
        record_id = record['result'][0]['id']
        record_type = record['result'][0]['type']
        proxied = record['result'][0]['proxied']
        return record_id, record_type, proxied
    except Exception as e:
        error(f"An error occurred: {e}")
        return None, None, None


def assemble_hosts_records(api_token: str, api_key: str, api_email: str, host_list: List[str]) -> Dict:
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

    actual_update_hosts = {}
    for host in host_list:
        domain = get_domain(host)
        if domain in zone_id_map:
            record_id, record_type, proxied = get_record_id_by_name(cf, zone_id_map[domain], host)
            if record_id:
                actual_update_hosts[host] = {
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
    return actual_update_hosts


def get_domain(fqdn: str) -> str:
    ext = tldextract.extract(fqdn)
    return f"{ext.domain}.{ext.suffix}"


def get_tlds(host_list: List[str]) -> set:
    return {get_domain(host) for host in host_list}


def update_cloudflare_dns_record(client: Cloudflare, host_record: Dict) -> bool:
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


def update_dns_records(api_token: str, api_key: str, api_email: str, actual_update_hosts: dict) -> bool:

    global previous_ip

    external_ip = get_external_ip()
    if not external_ip:
        error("Could not retrieve external IP address.")
        return False

    if (external_ip == previous_ip):
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
    save_current_ip(external_ip)
    return all(results)


def get_env_var(name: str) -> str:
    """Get required environment variable with validation."""
    value = os.getenv(name)
    if not value:
        error(f"{name} environment variable is not set.")
        raise EnvironmentError(f"{name} is required")
    return value


def save_current_ip(ip: str):
    """Save current IP as previous a file."""
    global previous_ip, previous_ip_filename
    if ip != previous_ip:
        with open('/app/previous_ip.txt', 'w') as f:
            f.write(ip)
        previous_ip = ip
        info(f"Previous IP updated to {ip}")
    else:
        info("IP has not changed, no update needed.")


def load_previous_ip() -> str:
    """Load previous IP from file."""
    global previous_ip, previous_ip_filename
    if os.path.exists(previous_ip_filename):
        with open(previous_ip_filename, 'r') as f:
            previous_ip = f.read().strip()
    else:
        save_current_ip('invalid')


def main():
    load_previous_ip()
    configure_logging()

    try:
        # Validate required environment variables
        api_token = get_env_var('CLOUDFLARE_API_TOKEN')
        api_key = get_env_var('CLOUDFLARE_API_KEY')
        api_email = get_env_var('CLOUDFLARE_API_EMAIL')

        host_list_str = os.getenv('HOST_LIST', '')
        if not host_list_str:
            error("HOST_LIST environment variable is not set.")
            return

        host_list = list(set([host.strip().lower() for host in host_list_str.split(',') if host.strip()]))
        try:
            update_interval = max(1, int(os.getenv('UPDATE_INTERVAL', '60')))
        except ValueError:
            warn("UPDATE_INTERVAL must be a valid integer. Using default value of 60 minutes.")
            update_interval = 60

    except (ValueError, TypeError) as e:
        error(f"Configuration error: {e}")
        return

    actual_update_hosts = assemble_hosts_records(api_token, api_key, api_email, host_list)

    if not actual_update_hosts:
        error("No valid hosts found to monitor. Exiting.")
        return

    interval_seconds = update_interval * 60  # Convert minutes to seconds

    info(f"Starting DNS update service. Will update every {update_interval} minutes.")
    info(f"Monitoring hosts: {list(actual_update_hosts.keys())}")

    while True:
        try:
            info(f"Updating DNS records at {time.strftime('%Y-%m-%d %H:%M:%S')}")
            success = update_dns_records(api_token, api_key, api_email, actual_update_hosts)

            if success:
                info("All DNS records updated successfully.")
            else:
                warn("Some DNS record updates failed.")
            write_health_status()
            info(f"Next update in {update_interval} minutes...")
            time.sleep(interval_seconds)

        except KeyboardInterrupt:
            warn("\nReceived interrupt signal. Shutting down...")
            break
        except Exception as e:
            error(f"Unexpected error during DNS update: {e}")
            info(f"Retrying in {update_interval} minutes...")
            time.sleep(interval_seconds)


if __name__ == "__main__":
    main()