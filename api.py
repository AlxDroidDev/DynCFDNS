from datetime import datetime, timezone

import uvicorn
from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.responses import JSONResponse

from cfupdater import get_updatable_hosts, get_last_update, get_previous_ip, get_last_check
from globals import API_PORT, UPDATE_INTERVAL, API_TOKEN

app = FastAPI(title="DynCFDNS API", version="1.0.0")
__UNAUTHORIZED = "Unauthorized"

def __format_datetime_iso8859(dt):
    """Format datetime to ISO-8859-1 compatible string."""
    if dt is None:
        return None
    if isinstance(dt, datetime):
        return dt.isoformat()
    return str(dt)


def __is_status_good() -> bool:
    last_check = get_last_check()
    return last_check and (datetime.now(timezone.utc) - last_check).total_seconds() <= (UPDATE_INTERVAL + 15)


def __verify_api_token(authorization: str = Header(None)):
    """Verify the API token from Authorization header."""
    if not API_TOKEN:
        raise HTTPException(status_code=503, detail="No API token configured")

    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header required")

    # Support both "Bearer TOKEN" and "TOKEN" formats
    token = authorization.replace("Bearer ", "").strip()

    if token != API_TOKEN:
        raise HTTPException(status_code=403, detail=__UNAUTHORIZED)

    return True


@app.get("/widget")
async def get_widget_data(authorized: bool = Depends(__verify_api_token)):
    """Return simplified data for homepage widget."""
    if not authorized:
        raise HTTPException(status_code=403, detail=__UNAUTHORIZED)

    try:
        valid_hosts = get_updatable_hosts()

        host_count = len(valid_hosts) if valid_hosts else 0
        # hosts = '\n'.join([host for host in valid_hosts if host])
        hosts = [host for host in valid_hosts] if valid_hosts else []
        is_active = 'active' if __is_status_good() else 'unhealthy'

        response_data = {
            'last_check': __format_datetime_iso8859(get_last_check()) or "Never",
            'last_update': __format_datetime_iso8859(get_last_update()) or "Never",
            'host_count': host_count,
            'hosts': hosts,
            'current_ip': get_previous_ip() or 'Unknown',
            'status': is_active
        }
        return JSONResponse(
            content=response_data,
            headers={"Content-Type": "application/json; charset=iso-8859-1"}
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve widget data: {str(e)}")


@app.get("/health")
async def health_check():
    """Simple health check endpoint."""
    if __is_status_good():
        return {"status": "ok"}
    else:
        return JSONResponse(
            content={"status": "unhealthy", "last_check": (__format_datetime_iso8859(get_last_check()) or 'Never')},
            status_code=503
        )


def start_api():
    """Start the API server."""
    if API_PORT <= 0:
        return
    uvicorn.run(app, host="0.0.0.0", port=API_PORT, access_log=False)

