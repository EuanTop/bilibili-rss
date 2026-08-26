FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    BILIBILI_RSS_HOST=0.0.0.0 \
    BILIBILI_RSS_PORT=8765 \
    BILIBILI_COOKIE_FILE=/run/secrets/bilibili.cookie \
    BILIBILI_DATA_DIR=/app/data

WORKDIR /app
COPY pyproject.toml uv.lock README.md LICENSE ./
COPY bilibili_rss_service ./bilibili_rss_service

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir .

EXPOSE 8765
VOLUME ["/app/data"]
CMD ["bilibili-rss", "serve"]
