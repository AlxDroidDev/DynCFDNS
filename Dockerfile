FROM python:3.13-alpine3.22

ENV APP_NAME='Dynamic Cloudflare DNS Updater' \
    APP_VERSION='1.0.0' \
    CLOUDFLARE_API_TOKEN="" \
    CLOUDFLARE_API_KEY="" \
    CLOUDFLARE_API_EMAIL="" \
    HOST_LIST="" \
    UPDATE_INTERVAL=60 \


WORKDIR /app
COPY main.py ./
COPY requirements.txt ./

RUN pip install --no-cache-dir -r requirements.txt

CMD ["python3", "main.py"]




