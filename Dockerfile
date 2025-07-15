FROM python:3.13-alpine3.22

WORKDIR /app

COPY api.py cfupdater.py globals.py healthcheck.py ilogger.py main.py requirements.txt LICENSE README.md ./

ENV USER=cfuser
ENV GROUPNAME=$USER \
    UID=9870 \
    GID=9870 \
    APP_NAME='Dynamic Cloudflare DNS Updater' \
    APP_VERSION='1.0.0' \
    CLOUDFLARE_API_EMAIL="" \
    HOST_LIST="" \
    UPDATE_INTERVAL=120 \
    API_PORT=5000 \
    ALLOW_CREATE_HOSTS=false


RUN addgroup --gid "$GID" "$GROUPNAME" && \
    adduser --disabled-password --gecos "" --home "$(pwd)" --ingroup "$GROUPNAME" --no-create-home --uid "$UID" $USER && \
    chown -R $USER:$GROUPNAME /app

#    apk add --no-cache --virtual .runtime-deps procps && \
#    rm -rf /var/cache/apk/* && \

USER cfuser

RUN pip install --no-cache-dir -r requirements.txt


HEALTHCHECK --interval=120s --timeout=10s --start-period=30s --retries=3 CMD python /app/healthcheck.py

CMD ["python3", "/app/main.py"]