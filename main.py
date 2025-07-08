import json
import os

import requests
import tldextract
from cloudflare import Cloudflare
import time
import signal
import sys

def signal_handler(sig, frame):
    print("\nGracefully shutting down...")
    sys.exit(0)


def get_external_ip():
    try:
        response = requests.get('https://api.ipify.org?format=json')
        response.raise_for_status()
        return response.json()['ip']
    except requests.RequestException as e:
        print(f"Error fetching external IP: {e}")
        return None


def get_record_id_by_name(cf, zone_id, record_name) -> (str, str, str):
    try:
        record = json.loads(cf.dns.records.list(zone_id=zone_id, name=record_name).model_dump_json())
        if record['result_info']['count'] != 1:
            print(f"Either more than one or No DNS record found for {record_name} in zone {zone_id}")
            return None, None, None
        record_type = record['result'][0]['type']
        record_id = record['result'][0]['id']
        proxied = record['result'][0]['proxied']
        return record_id, record_type, proxied
    except Exception as e:
        print(f"An error occurred: {e}")
        return None, None, None


def mount_hosts_records(api_token: str, api_key: str, api_email: str, host_list: list) -> dict:
    cf = Cloudflare(api_token=api_token, api_email=api_email, api_key=api_key)
    try:
        zones = cf.zones.list()
        if not zones.result:
            print("No zones found.")
            return {}
    except Exception as e:
        print(f"Error fetching zones: {e}")
        return {}

    zone_id_map = {zone.name: zone.id for zone in zones.result if zone.name in get_tlds(host_list)}

    if not zone_id_map:
        print("No matching zones found for the provided host list.")
        return {}

    actual_update_hosts = {}
    for host in host_list:
        domain = get_domain(host)
        if domain in zone_id_map:
            record_type, record_id, proxied = get_record_id_by_name(cf, zone_id_map[domain], host)
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
                print(f"No DNS record found for {host} in zone {zone_id_map[domain]}")
        else:
            print(f"Domain {domain} not found in Cloudflare zones for host {host}")
    return actual_update_hosts


def get_domain(fqdn):
    ext = tldextract.extract(fqdn)
    return f"{ext.domain}.{ext.suffix}"


def get_tlds(host_list) -> set:
    return {get_domain(host) for host in host_list}


def update_cloudflare_dns_record(client: Cloudflare, host_record) -> bool:
    try:
        record = client.dns.records.update(
            dns_record_id=host_record['record_id'],
            zone_id=host_record['zone_id'],
            content=host_record['content'],
            type=host_record['type'],
            name=host_record['name']
        )
        print(f"Updated DNS record for {host_record['name']} to {host_record['content']}")
        return record is not None and record.get('success', False)
    except Exception as e:
        print(f"Error updating DNS record for {host_record['name']}: {e}")
        return False


def update_dns_records(api_token: str, api_key: str, api_email: str, actual_update_hosts: dict) -> bool:
    cf = Cloudflare(api_token=api_token, api_email=api_email, api_key=api_key)
    external_ip = get_external_ip()
    if not external_ip:
        print("Could not retrieve external IP address.")
        return False

    result = True
    for host_info in actual_update_hosts:
        host_record = {
            'zone_id': host_info['zone_id'],
            'type': host_info['record_type'],
            'name': host_info['host'],
            'content': external_ip,
            'proxied': host_info['proxied']
        }
        result = result & update_cloudflare_dns_record(cf, host_record)
    return result

def main():
    host_list = list(set([host.strip().lower() for host in os.getenv('HOST_LIST', '').split(',')]))
    update_interval = int(os.getenv('UPDATE_INTERVAL', '60')) # 60 minutes | 1 hour
    api_token = os.getenv('CLOUDFLARE_API_TOKEN')
    if not api_token:
        print("CLOUDFLARE_API_TOKEN environment variable is not set.")
        return
    api_key = os.getenv('CLOUDFLARE_API_KEY')
    if not api_key:
        print("CLOUDFLARE_API_KEY environment variable is not set.")
        return
    api_email = os.getenv('CLOUDFLARE_API_EMAIL')
    if not api_email:
        print("CLOUDFLARE_API_EMAIL environment variable is not set.")
        return

    actual_update_hosts = mount_hosts_records(api_token, api_key, api_email, host_list)

    update_interval = int(update_interval)
    if update_interval==0:
        update_interval = 60  # Default to 60 minutes if not set or invalid
    interval_seconds = update_interval * 60  # Convert minutes to seconds

    print(f"Starting DNS update service. Will update every {update_interval} minutes.")
    print(f"Monitoring hosts: {list(actual_update_hosts.keys())}")

    while True:
        try:
            print(f"Updating DNS records at {time.strftime('%Y-%m-%d %H:%M:%S')}")
            success = update_dns_records(api_token, api_key, api_email, actual_update_hosts)

            if success:
                print("All DNS records updated successfully.")
            else:
                print("Some DNS record updates failed.")

            print(f"Next update in {update_interval} minutes...")
            time.sleep(interval_seconds)

        except KeyboardInterrupt:
            print("\nReceived interrupt signal. Shutting down...")
            break
        except Exception as e:
            print(f"Unexpected error during DNS update: {e}")
            print(f"Retrying in {update_interval} minutes...")
            time.sleep(interval_seconds)

