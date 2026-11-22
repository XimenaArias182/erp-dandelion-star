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
 && rm -rf /var/lib/apt/lists/*

FROM system-deps AS python-deps

WORKDIR /app

COPY requirements.txt .
RUN pip install --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt

FROM python-deps AS app

WORKDIR /app

COPY . .

RUN SECRET_KEY=build-placeholder-key \
    DATABASE_URL=sqlite:////tmp/build.sqlite3 \
    DJANGO_SETTINGS_MODULE=core.settings_prod \
    python manage.py collectstatic --noinput

RUN chmod +x docker-entrypoint.sh

EXPOSE 10000

ENTRYPOINT ["./docker-entrypoint.sh"]