import api
import threading
import sys
import cfupdater

if __name__ == '__main__':
    # Start API in background thread
    sys.tracebacklimit = 0
    api_thread = threading.Thread(target=api.start_api)
    api_thread.daemon = True
    api_thread.start()

    cfupdater.main()
