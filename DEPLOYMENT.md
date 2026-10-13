# Deploying UK Weather on Render

The Dockerfile builds Tailwind/TypeScript assets with Node and runs Django with
Gunicorn as an unprivileged user. Its Python image includes GDAL, GEOS and PROJ.
WhiteNoise serves collected static files. Secrets are excluded from the image.

## Render setup

1. Commit the deployment files and push to your Git repository.
2. Create a Render Blueprint from `render.yaml`. Review costs before applying:
   it defines a paid web service and paid PostgreSQL database in Frankfurt,
   with 5 GB of database storage. Nothing is deployed just by adding this file.
3. Supply `MAP_STYLE_URL` when prompted. Use a licensed MapLibre-compatible
   style URL, including any browser-safe provider token. This URL is visible to
   visitors: do not use a secret server API key. Restrict browser tokens to your
   site in the provider dashboard, and retain the required map attribution.
4. Render generates `DJANGO_SECRET_KEY` and supplies the internal `DATABASE_URL`.
   It sets `DJANGO_DEBUG=false`; the app allows Render's assigned hostname.
5. The pre-deploy command runs migrations. The initial migration enables PostGIS
   before creating geographic tables. For an existing database whose initial
   migration was already applied, enable it explicitly if necessary:
   `CREATE EXTENSION IF NOT EXISTS postgis;`.
6. Import your boundary and settlement datasets through the Render Shell using
   the management commands documented in README.md. Copy/download the datasets
   into the service for this import; they are not included in the repository.
   Import boundaries first, then settlements. Until imported, the map has no
   authority polygons or settlement points.
7. Create an administrator with `python manage.py createsuperuser` if needed.
8. Check region search, map selection, forecasts and static files in the browser.

For a custom domain, set `DJANGO_ALLOWED_HOSTS` to the comma-separated hostnames.
Set `DJANGO_CSRF_TRUSTED_ORIGINS` to any additional trusted HTTPS origins required
by your setup. HTTPS redirects and secure cookies are enabled in production;
the proxy-header configuration assumes Render's trusted reverse proxy.

## Local development

Keep your existing `.env` private. `.env.example` documents the supported local
variables without real credentials. Compose now uses PostgreSQL 17 with PostGIS.
Do not delete an existing database volume to enable the extension; connect to
the existing database and enable PostGIS explicitly if needed.

## Checks

With dependencies and a test-capable PostGIS database configured:

```sh
npm ci
npm run build
python manage.py check
pytest
```

In the deployed production environment:

```sh
python manage.py check --deploy
```

The Open-Meteo SQLite response cache is stored under `/tmp` in the container.
It is disposable, local to each instance, and resets on redeploy/restart. It
does not need a persistent disk; geographic data stays in managed PostgreSQL.

Render references:
- https://render.com/docs/blueprint-spec
- https://render.com/docs/docker
- https://render.com/docs/postgresql-extensions
