# UK Weather

An interactive UK weather application built with Django, HTMX, Tailwind CSS,
TypeScript, and PostgreSQL.

## Project layout

```text
apps/
  core/                 # Home page and shared application views
  locations/            # Location search and saved locations
  weather/              # Forecast UI, provider client, and transformations
config/
  settings/             # Shared, development, and production settings
  urls.py
assets/
  css/input.css          # Tailwind source
  ts/app.ts              # TypeScript source
static/                  # Compiled browser assets
templates/
  components/            # Reusable global template fragments
tests/                   # Project-level smoke tests
compose.yml              # Local PostgreSQL service
manage.py
package.json
pyproject.toml          # Pytest and Ruff configuration
tsconfig.json
```

## Local setup

1. Copy `.env.example` to `.env`.
2. Start PostgreSQL with `docker compose up -d`.
3. Install frontend dependencies with `npm install`.
4. Build assets with `npm run build`.
5. Run migrations with `python manage.py migrate`.
6. Start Django with `python manage.py runserver`.
