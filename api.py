from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
import uvicorn

from cfupdater import last_check, last_update, updatable_hosts, previous_ip
from globals import API_PORT, UPDATE_INTERVAL

app = FastAPI(title="DynCFDNS API", version="1.0.0")


def format_datetime_iso8859(dt):
    """Format datetime to ISO-8859-1 compatible string."""
    if dt is None:
        return None
    if isinstance(dt, datetime):
        return dt.isoformat()
    return str(dt)


def is_status_good() -> bool:
    return last_check and (datetime.now() - last_check).total_seconds() <= (UPDATE_INTERVAL + 15)


@app.get("/widget")
async def get_widget_data():
    """Return simplified data for homepage widget."""
    try:
        host_count = len(updatable_hosts) if updatable_hosts else 0
        hosts = '\n'.join([host for host in updatable_hosts if host])

        is_active = 'active' if is_status_good() else 'unhealthy'

        response_data = {
            'last_check': format_datetime_iso8859(last_check),
            'last_update': format_datetime_iso8859(last_update),
            'host_count': host_count,
            'hosts': hosts if updatable_hosts else 'None',
            'current_ip': previous_ip or 'Unknown',
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
    if is_status_good():
        return {"status": "ok"}
    else:
        return JSONResponse(
            content={"status": "unhealthy", "last_check": format_datetime_iso8859(last_check)},
            status_code=503
        )


def start_api():
    """Start the API server."""
    if API_PORT <= 0:
        return
    uvicorn.run(app, host="0.0.0.0", port=API_PORT, access_log=False)