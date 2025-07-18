# DynCFDNS Homepage.dev Integration

This guide explains how to integrate DynCFDNS with homepage.dev dashboard for monitoring your dynamic DNS status.

## Prerequisites

- DynCFDNS running with API enabled (`API_PORT > 0`)
- Homepage.dev dashboard installed and configured
- DynCFDNS API token (auto-generated on first run or manually configured)

## Configuration

### 1. Get Your API Token

The API token is automatically generated when DynCFDNS starts. Check the console output for:
```
Generated new API token: YOUR_TOKEN_HERE
```

Alternatively, you can set it manually via environment variable:
```bash
export API_TOKEN="your_custom_token_here"
```

### 2. Configure Homepage.dev Service

Add this configuration to your homepage.dev `services.yaml`. It uses the `customapi` widget type to fetch data from DynCFDNS API, and it allows you to customize the displayed fields.

```yaml
- DNS Management:
    - DynCFDNS:
        icon: cloudflare.png
        href: http://your-dyncfdns-host:5000
        description: Dynamic CloudFlare DNS updater
        widget:
          type: customapi
          url: http://your-dyncfdns-host:5000/widget
          headers:
            Authorization: Bearer YOUR_API_TOKEN_HERE
          mappings:
            - field: last_check
              label: Last Check
              format: relativeDate
            - field: last_update
              label: Last Update
              format: relativeDate
            - field: host_count
              label: Managed Hosts
            - field: current_ip
              label: Current IP
```

### 3. Widget Data Format

The `/widget` endpoint returns data in this format:

```json
{
  "last_check": "2025-01-20T10:30:00",
  "last_update": "2025-01-20T10:15:00", 
  "host_count": 2,
  "hosts": "home.example.com\nserver.example.com",
  "current_ip": "203.0.113.1",
  "status": "active"
}
```

## Advanced Configuration

### Multiple Instances

For multiple DynCFDNS instances:

```yaml
- DNS Management:
    - Home DynCFDNS:
        widget:
          type: customapi
          url: http://home-dyncfdns:5000/widget
          headers:
            Authorization: Bearer HOME_TOKEN
    - Server DynCFDNS:
        widget:
          type: customapi
          url: http://server-dyncfdns:5001/widget
          headers:
            Authorization: Bearer SERVER_TOKEN
```

## Troubleshooting

### Authentication Issues

**401 Unauthorized**: Missing Authorization header
- Ensure the `Authorization: Bearer TOKEN` header is included
- Verify the token is correctly copied

**403 Forbidden**: Invalid token
- Check the token matches what DynCFDNS generated/configured
- Regenerate token by removing `./config/.config.json` and restarting

### Connection Issues

**503 Service Unavailable**: API disabled
- Ensure `API_PORT > 0` in DynCFDNS configuration
- Check DynCFDNS is running and accessible

**Connection refused**: Network issues
- Verify the URL and port in widget configuration
- Check firewall rules and network connectivity

### Widget Display Issues

**No data showing**: Check homepage.dev logs
- Verify the widget configuration syntax
- Test the API endpoint manually with curl:

```bash
curl -H "Authorization: Bearer YOUR_TOKEN" http://localhost:5000/widget
```

## Security Considerations

- **Use HTTPS**: Configure reverse proxy with SSL/TLS in production
- **Network Isolation**: Restrict API access to trusted networks only
- **Token Management**: Store tokens securely, rotate regularly
- **Firewall Rules**: Limit access to API port to homepage.dev host only


For more information about DynCFDNS configuration, see the main project README.md.
