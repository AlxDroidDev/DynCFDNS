FROM python:3.13-alpine3.22

ARG CFUSER=cfuser
ARG CFUID=9870
ARG CFVERSION=1.0.1

LABEL org.opencontainers.image.authors="alxdroiddev@gmail.com"
LABEL org.opencontainers.image.url="https://github.com/AlxDroidDev/DynCFDNS"
LABEL org.opencontainers.image.documentation="https://github.com/AlxDroidDev/DynCFDNS/blob/main/README.md"
LABEL org.opencontainers.image.source="https://raw.githubusercontent.com/AlxDroidDev/DynCFDNS/refs/heads/main/Dockerfile"
LABEL org.opencontainers.image.vendor="AlxDroidDev"
LABEL org.opencontainers.image.licenses="AGPL-3.0-only"
LABEL org.opencontainers.image.title="DynCFDNS"
LABEL org.opencontainers.image.description="Dynamic Cloudflare DNS Updater is a simple Python application that updates DNS records on Cloudflare based on the current public IP address of the host machine. It supports multiple hosts and can be configured to run at specified intervals. It also features a simple REST API for monitoring DNS records and checking the current IP address, allowing it to be integrated to dashboards such as homepage.dev."
LABEL org.opencontainers.image.version="${CFVERSION}"

WORKDIR /app

ENV USER=${CFUSER} \
    UID=${CFUID} \
    GROUPNAME=${CFUSER} \
    GID=${CFUID} \
    APP_NAME='Dynamic Cloudflare DNS Updater' \
    APP_VERSION=${CFVERSION} \
    CLOUDFLARE_API_EMAIL="" \
    HOST_LIST="" \
    UPDATE_INTERVAL=120 \
    API_PORT=5000 \
    ALLOW_CREATE_HOSTS=false \
    PATH="$PATH:/app/.local/bin"

# The apk update & upgrade are required in order to remove the CVE appointments related to libssl3
# They do increase the image size, but they are necessary for security reasons.
RUN addgroup --gid "$GID" "$GROUPNAME" && \
    adduser --disabled-password --gecos "" --home "$(pwd)" --ingroup "$GROUPNAME" --no-create-home --uid "$UID" $USER && \
    chown -R $USER:$GROUPNAME $(pwd) && \
    apk update && \
    apk upgrade && \
    rm -rf /var/cache/apk/*

COPY --chown=$UID:$GID --chmod=440 *.py requirements.txt LICENSE README.md ./

USER cfuser

RUN pip install --no-cache-dir -r requirements.txt && \
    pip uninstall -y watchfiles && \
    rm requirements.txt

HEALTHCHECK --interval=120s --timeout=10s --start-period=30s --retries=3 CMD python /app/healthcheck.py

CMD ["python3", "/app/main.py"]