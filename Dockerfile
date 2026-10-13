FROM node:22-bookworm-slim AS frontend
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY assets ./assets
COPY templates ./templates
COPY apps ./apps
RUN mkdir -p static/css static/js && npm run build

FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    DJANGO_DEBUG=false OPEN_METEO_CACHE_NAME=/tmp/openmeteo-cache
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgdal32 libgeos-c1v5 libproj25 && rm -rf /var/lib/apt/lists/*
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
COPY --from=frontend /app/static/css ./static/css
COPY --from=frontend /app/static/js ./static/js
# Static collection needs settings but does not connect to a database.
RUN DJANGO_DEBUG=true DATABASE_URL=postgresql://build:build@localhost/build \
    python manage.py collectstatic --noinput
RUN useradd --create-home app
USER app
CMD ["sh", "-c", "exec gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers 2 --threads 4 --timeout 120 --access-logfile - --error-logfile -"]
