# Dockerfile
# ERP Django con WeasyPrint
# Base: Python 3.11 sobre Debian Bookworm slim

FROM python:3.11-slim-bookworm AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

FROM base AS system-deps

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libpangocairo-1.0-0 \
    libcairo2 \
    libcairo-gobject2 \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    shared-mime-info \
    fonts-liberation \
    fonts-dejavu-core \
    libjpeg62-turbo-dev \
    libpng-dev \
    libwebp-dev \
    zlib1g-dev \
    libpq-dev \
    gcc \
    curl \
 && fc-cache -f -v 2>/dev/null && chmod -R 777 /var/cache/fontconfig 2>/dev/null || true \
 && rm -rf /var/lib/apt/lists/*

FROM system-deps AS python-deps

WORKDIR /app

COPY requirements.txt .
RUN pip install --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt

FROM python-deps AS app

WORKDIR /app

COPY . .

RUN chmod +x docker-entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["./docker-entrypoint.sh"]
