from flask import Flask, jsonify
from datetime import datetime
from cfupdater import last_check, last_update, updatable_hosts, previous_ip
from globals import API_PORT

app = Flask(__name__)


def format_datetime_iso8859(dt):
    """Format datetime to ISO-8859-1 compatible string."""
    if dt is None:
        return None
    if isinstance(dt, datetime):
        return dt.isoformat()
    return str(dt)


@app.route('/status', methods=['GET'])
def get_status():
    """Return DNS update status information."""
    try:
        response_data = {
            'last_check': format_datetime_iso8859(last_check),
            'last_update': format_datetime_iso8859(last_update),
            'updatable_hosts': updatable_hosts,
            'previous_ip': previous_ip
        }

        response = jsonify(response_data)
        response.headers['Content-Type'] = 'application/json; charset=iso-8859-1'
        return response

    except Exception as e:
        return jsonify({'error': 'Failed to retrieve status', 'details': str(e)}), 500


@app.route('/health', methods=['GET'])
def health_check():
    """Simple health check endpoint."""
    return jsonify({'status': 'ok'}), 200


@app.errorhandler(Exception)
def handle_unhandled_exception(e):
    """Global error handler for unhandled exceptions."""
    return jsonify({'error': 'An unexpected error occurred', 'details': str(e)}), 500


def start_api():
    """Start the API server in a separate thread."""
    from waitress import serve
    serve(app, host="0.0.0.0", port=API_PORT, threads=1, expose_tracebacks=False)
    # app.run(host='0.0.0.0', port=5000, debug=False)
