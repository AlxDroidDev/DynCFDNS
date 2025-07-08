FROM python:3.13-alpine3.22

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt && \
    rm -rf /root/.cache && \
    apk add --no-cache --virtual .runtime-deps procps && \
    rm -rf /var/cache/apk/*

COPY main.py ./

ENV APP_NAME='Dynamic Cloudflare DNS Updater' \
    APP_VERSION='1.0.0' \
    CLOUDFLARE_API_EMAIL="" \
    HOST_LIST="" \
    UPDATE_INTERVAL=60

HEALTHCHECK --interval=1m --timeout=10s --start-period=30s --retries=3 CMD pgrep -f main.py > /dev/null || exit 1

CMD ["python3", "/app/main.py"]