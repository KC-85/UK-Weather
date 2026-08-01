# UK Weather

UK Weather is an interactive, map-first weather application for the United
Kingdom. It combines official administrative boundaries stored in PostGIS with
city and town data, an interactive MapLibre map, and weather forecasts from
Open-Meteo's UK Met Office model.

The user can explore local-authority boundaries, search for an authority, hover
over regions and settlements, and click either a boundary or settlement to load
current conditions plus hourly and seven-day forecasts. Settlements provide
geographical context, while forecasts remain attached to local authorities.

> [!IMPORTANT]
> This project is currently configured for local development. The Django
> settings contain development-only values and must be hardened before any
> public deployment. See [Production considerations](#production-considerations).

## Contents

- [Current features](#current-features)
- [Technology](#technology)
- [Architecture](#architecture)
- [Data model](#data-model)
- [Project structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Local setup](#local-setup)
- [PostGIS and spatial data](#postgis-and-spatial-data)
- [Importing authority boundaries](#importing-authority-boundaries)
- [Importing settlements](#importing-settlements)
- [Running the application](#running-the-application)
- [Frontend development](#frontend-development)
- [Application endpoints](#application-endpoints)
- [Weather integration](#weather-integration)
- [Testing and quality checks](#testing-and-quality-checks)
- [Troubleshooting](#troubleshooting)
- [Data sources and attribution](#data-sources-and-attribution)
- [Current limitations and roadmap](#current-limitations-and-roadmap)
- [Production considerations](#production-considerations)
- [Licence](#licence)

## Current features

### Interactive map

- MapLibre GL map centred on the UK.
- Local-authority boundary fill and outline layers.
- Boundary data loaded only for the visible bounding box.
- Zoom-dependent geometry simplification to reduce GeoJSON payload size.
- Aborted map requests when the user moves again before an earlier request
  finishes.
- Region hover tooltip and selected-region highlighting.
- Clickable authority boundaries.
- Navigation and zoom controls.

### Cities and towns

- OS Open Names city and town points stored in PostGIS.
- Bounding-box and zoom-aware settlement loading.
- Cities visible at national zoom levels; towns are added from zoom `5.5`.
- Different dot sizes and colours for cities and towns.
- City labels from zoom `4` and town labels from zoom `7`.
- Settlement tooltips show the name, type, and associated authority.
- Clicking a settlement selects its associated authority, so weather is still
  forecast by authority rather than by settlement.
- Welsh and other bilingual names are preserved as alternate names during
  import where available.

### Search and dynamic UI

- HTMX-powered region/local-authority search.
- Minimum two-character query, ranked by exact, prefix, then partial match.
- A maximum of eight search results.
- Selecting a result moves the map to its boundary and loads its panel.
- Loading, retry, and error states for the selected-region panel.
- Accessible status text and `aria-busy` state while requests are running.

### Weather

- Current conditions for the selected authority.
- Next 24 hours of hourly forecast data.
- Seven-day daily forecast.
- Local SVG weather icons with day/night variants.
- WMO weather-code descriptions.
- Temperature, feels-like temperature, humidity, precipitation, cloud cover,
  wind speed, direction, and gusts where appropriate.
- One-hour response cache, retry handling, and a ten-second upstream timeout.
- No Open-Meteo API key is required.

## Technology

| Area | Technology | Purpose |
| --- | --- | --- |
| Backend | Django 6 | Routing, templates, models, forms, views, and admin |
| Spatial backend | GeoDjango | Spatial fields, transformations, and queries |
| Database | PostgreSQL + PostGIS | Boundaries, points, containment, and bounding-box queries |
| Dynamic HTML | HTMX 2 | Search and weather-panel partial updates |
| Map | MapLibre GL JS 6 | Interactive vector-style map and GeoJSON layers |
| Styling | Tailwind CSS 4 | Utility-first application styling |
| Browser code | TypeScript | Map interactions and HTMX orchestration |
| Asset build | esbuild | TypeScript bundling and minification |
| Weather provider | Open-Meteo | UKMO current, hourly, and daily forecast data |
| Tests | pytest + pytest-django | Model, view, importer, client, and transformer tests |
| Linting | Ruff | Python correctness, style, and import checks |

The project intentionally uses ordinary `venv` and `pip`; it does **not** use
`uv`.

## Architecture

```mermaid
flowchart LR
    B[Browser] -->|HTML and HTMX| D[Django]
    B -->|bbox and zoom| G[GeoJSON endpoints]
    G --> P[(PostgreSQL + PostGIS)]
    D --> P
    D -->|authority forecast point| O[Open-Meteo UKMO API]
    O -->|current, hourly, daily| D
    G --> M[MapLibre layers]
    M -->|authority selected| D
```

The map is deliberately split into two geographical concepts:

1. **Regions** are polygons representing nations, regions, or local
   authorities. They define selectable forecast areas.
2. **Settlements** are city/town points used for map context and labels. Each
   imported point is associated with the authority whose polygon covers it.

When a user clicks a settlement, the browser sends the settlement's associated
authority code through the same selection flow as a polygon click. The weather
request then uses the authority's `forecast_point`.

## Data model

### `Region`

| Field | Description |
| --- | --- |
| `code` | Unique official identifier, such as an ONS geography code |
| `name` | Display name |
| `region_type` | `nation`, `region`, or `local_authority` |
| `parent` | Optional self-reference for a future geography hierarchy |
| `boundary` | `MultiPolygonField`, SRID 4326 |
| `forecast_point` | `PointField`, SRID 4326, used for the weather request |

The boundary importer computes `forecast_point` using the polygon's point on
surface. Unlike a simple centroid, a point on surface is guaranteed to lie
inside the geometry.

### `Settlement`

| Field | Description |
| --- | --- |
| `source` | Currently `os_open_names` |
| `source_id` | Stable identifier supplied by the source dataset |
| `name` | Preferred display name |
| `alternate_name` | Optional bilingual/alternate name |
| `settlement_type` | `city`, `town`, `village`, or `hamlet` |
| `country` | England, Scotland, Wales, or Northern Ireland |
| `location` | `PointField`, SRID 4326 |
| `population` | Optional; OS Open Names does not currently populate it |
| `region` | Nullable foreign key to the covering `Region` |

`source` and `source_id` are unique together, which makes repeat imports safe.
The default importer currently loads only cities and towns.

### `SavedLocation`

`SavedLocation` stores a user-defined name, point, optional authority, and
creation time. Names are unique per user. The model and admin integration are
present, but the end-user save-location workflow has not yet been built.

## Project structure

```text
UK-Weather/
├── apps/
│   ├── core/
│   │   ├── templates/core/home.html       # Main map page
│   │   ├── urls.py
│   │   └── views.py
│   ├── locations/
│   │   ├── management/commands/
│   │   │   ├── import_regions.py          # Boundary importer
│   │   │   └── import_settlements.py      # OS Open Names importer
│   │   ├── migrations/
│   │   ├── templates/locations/partials/  # Search and region panel
│   │   ├── tests/
│   │   ├── admin.py
│   │   ├── forms.py
│   │   ├── models.py
│   │   ├── urls.py
│   │   └── views.py                       # Search and GeoJSON endpoints
│   └── weather/
│       ├── services/
│       │   ├── client.py                  # Open-Meteo client/cache/retries
│       │   ├── exceptions.py
│       │   ├── provider.py
│       │   └── transformers.py            # SDK response normalization
│       ├── templates/weather/partials/
│       ├── tests/
│       ├── types/forecast.py              # Application forecast types
│       ├── urls.py
│       └── views.py
├── assets/
│   ├── css/input.css                       # Tailwind source
│   └── ts/
│       ├── app.ts                          # HTMX and selection coordination
│       └── map.ts                          # MapLibre map, sources, and layers
├── config/
│   ├── settings.py
│   ├── urls.py
│   ├── asgi.py
│   └── wsgi.py
├── static/
│   ├── css/output.css                      # Generated Tailwind output
│   ├── icons/weather.svg                   # Local SVG symbol sprite
│   └── js/                                 # Generated JS and MapLibre worker
├── templates/
│   ├── components/
│   ├── 400.html
│   ├── 404.html
│   ├── 500.html
│   └── base.html
├── tests/                                  # Project-level smoke/home tests
├── compose.yml
├── manage.py
├── package.json
├── package-lock.json
├── pyproject.toml
├── requirements.txt
└── tsconfig.json
```

Files in `assets/` are the editable frontend sources. Files in `static/css/`
and `static/js/` are build output and should be regenerated with npm rather
than edited manually.

## Prerequisites

- Python 3.12 or newer.
- PostgreSQL with the PostGIS extension available.
- A database user allowed to connect, create tables, and use PostGIS types.
- GDAL, GEOS, and PROJ system libraries for GeoDjango and the import commands.
- Node.js and npm for building frontend assets.
- `psql` if you want to use `python manage.py dbshell`.
- Internet access in the browser for the current MapLibre demonstration style.
- Internet access from Django for Open-Meteo forecast requests.

On Ubuntu/Debian, the GIS and PostgreSQL client tools can normally be installed
with:

```bash
sudo apt update
sudo apt install gdal-bin libgdal-dev libgeos-dev proj-bin libproj-dev postgresql-client
```

On Fedora-based laptops, the GIS and PostgreSQL client tools can normally be installed
with:

```bash
sudo dnf update
sudo dnf install gdal-bin libgdal-dev libgeos-dev proj-bin libproj-dev postgresql-client
```

Package names differ on other operating systems. Installing the Python `GDAL`
package alone is not a substitute for the native GDAL shared library required
by GeoDjango.

## Local setup

### 1. Clone and enter the project

```bash
git clone <repository-url>
cd UK-Weather
```

### 2. Create your virtual environment

Create the environment however you prefer. A standard `venv` setup is:

```bash
python3 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
```

On Windows PowerShell, activation is usually:

```powershell
venv\Scripts\Activate.ps1
```

### 3. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 4. Install frontend dependencies

The lock file is committed, so `npm ci` provides the most reproducible install:

```bash
npm ci
```

Use `npm install` instead when intentionally updating dependencies.

### 5. Create `.env`

There is currently no `.env.example`; create `.env` in the repository root:

```dotenv
DATABASE_URL=postgresql://USER:PASSWORD@HOST:PORT/DATABASE_NAME
```

For a hosted database that requires TLS, the URL may look like:

```dotenv
DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/DATABASE_NAME?sslmode=require
```

URL-encode reserved characters in usernames or passwords. Never commit `.env`;
it is excluded by `.gitignore`.

`config/settings.py` loads this file with `python-dotenv`, then parses
`DATABASE_URL` using `dj-database-url` and forces Django's PostGIS backend. A
missing `DATABASE_URL` will prevent Django from starting.

### 6. Check the database and PostGIS

```bash
python manage.py dbshell
```

At the `psql` prompt:

```sql
SELECT PostGIS_Version();
```

Exit with `\q`. A version string confirms that the connected database supports
PostGIS.

### 7. Apply migrations

```bash
python3 manage.py migrate
```

### 8. Build frontend assets

```bash
npm run build
```

### 9. Optionally create an admin user

```bash
python3 manage.py createsuperuser
```

The application can now run, but the map will have no authority or settlement
data until the import commands below have been used.

## PostGIS and spatial data

All stored application geometry uses WGS 84 longitude/latitude (`SRID 4326`),
which matches GeoJSON and MapLibre.

PostGIS is used for:

- `MultiPolygon` authority boundaries.
- Point-on-surface forecast coordinates.
- City/town point storage.
- Bounding-box intersection queries.
- Assigning each settlement to the authority polygon that covers it.
- Server-side topology-preserving geometry simplification.

### Note about `compose.yml`

The current `compose.yml` uses `postgres:17-alpine`, which is standard
PostgreSQL and does **not** bundle PostGIS. It is therefore not sufficient for
the current GeoDjango schema as written. Use the existing hosted PostGIS
database, install PostGIS locally, or change the service to an appropriate
PostGIS-enabled image before initializing a fresh local development database.

Do not point migrations or import commands at a database whose data you are not
prepared to modify.

## Importing authority boundaries

Import authority polygons before settlements. The settlement importer uses
those polygons to associate every city/town with its covering authority.

The boundary command accepts GeoJSON, GeoPackage, and other formats supported by
GDAL:

```bash
python3 manage.py import_regions SOURCE \
  --code-field FIELD \
  --name-field FIELD \
  --region-type local_authority \
  --layer LAYER
```

For the Counties and Unitary Authorities GeoPackage discussed during this
project, the command is shaped like this:

```bash
python3 manage.py import_regions /path/to/counties_and_unitary_authorities.gpkg \
  --layer CTYUA_DEC_2025_UK_BUC \
  --code-field CTYUA25CD \
  --name-field CTYUA25NM \
  --region-type local_authority
```

`--layer` can be either a layer name or a zero-based layer index and defaults to
`0`. Valid region types are:

- `nation`
- `region`
- `local_authority`

The command:

1. Validates that the source, layer, and named fields exist.
2. Reads each source geometry through GDAL.
3. Transforms it to SRID 4326.
4. Converts `Polygon` geometry to `MultiPolygon` when necessary.
5. Rejects empty, invalid, or non-polygon geometry.
6. Calculates a forecast point on the polygon surface.
7. Creates or updates the `Region` identified by its official code.

The entire import runs inside a transaction. Re-running it is idempotent: a
known code is updated instead of duplicated.

Useful inspection command for a GeoPackage:

```bash
ogrinfo -so /path/to/file.gpkg LAYER_NAME
```

That displays the layer geometry, coordinate reference system, and available
field names before import.

## Importing settlements

Download **OS Open Names** in GeoPackage format and extract it. Then first run a
small validation-only import:

```bash
python3 manage.py import_settlements /path/to/opname_gb.gpkg \
  --limit 20 \
  --dry-run
```

If that succeeds, validate the complete city/town selection without writing:

```bash
python3 manage.py import_settlements /path/to/opname_gb.gpkg --dry-run
```

Finally, import it:

```bash
python3 manage.py import_settlements /path/to/opname_gb.gpkg
```

The defaults are equivalent to:

```bash
python3 manage.py import_settlements /path/to/opname_gb.gpkg \
  --types City Town
```

Options:

| Option | Meaning |
| --- | --- |
| `--types` | One or more supported OS local types; defaults to `City Town` |
| `--limit N` | Process at most `N` matching rows; useful for verification |
| `--dry-run` | Read, validate, and transform without writing to PostGIS |

The importer reads only `populatedPlace` records from the GeoPackage's
`named_place` layer. It decodes the actual GeoPackage geometry, validates the
expected British National Grid source SRID (`27700`), and transforms each point
to SRID 4326. It does not use the GeoPackage's display envelope as a substitute
for the point geometry.

After bulk upserting the points in batches, the command uses PostGIS coverage
queries to associate each one with a `local_authority` boundary. It reports how
many rows were created, updated, and left without a matching authority.

Repeat imports are safe because records are upserted by `(source, source_id)`.
You can rerun the command when a newer OS Open Names release is downloaded.

> [!NOTE]
> OS Open Names covers Great Britain. A separate compatible source is needed to
> provide equivalent settlement coverage for Northern Ireland.

## Running the application

Start Django:

```bash
python3 manage.py runserver
```

Then open:

- Application: <http://127.0.0.1:8000/>
- Admin: <http://127.0.0.1:8000/admin/>

Suggested first manual check:

1. Confirm the basemap and authority outlines appear.
2. Hover an authority and check its name tooltip.
3. Search for an authority and select it.
4. Confirm current, hourly, and daily weather load.
5. Zoom in until town points and labels appear.
6. Click a city or town and confirm its authority is selected.

## Frontend development

### Build everything once

```bash
npm run build
```

This runs both the Tailwind and TypeScript builds. The TypeScript build also
copies MapLibre's worker modules into `static/js/` so they can be served locally.

### Watch Tailwind

```bash
npm run css:watch
```

### Watch TypeScript

```bash
npm run ts:watch
```

A convenient development setup uses three terminals:

```text
Terminal 1: source venv/bin/activate && python manage.py runserver
Terminal 2: npm run css:watch
Terminal 3: npm run ts:watch
```

HTMX is currently loaded from a CDN in `templates/base.html`. The MapLibre
worker is served locally, while the current demonstration map style is loaded
from `https://demotiles.maplibre.org/style.json`.

## Application endpoints

| Method | Path | Response/purpose |
| --- | --- | --- |
| `GET` | `/` | Main interactive map page |
| `GET` | `/admin/` | Django administration |
| `GET` | `/locations/search/?query=...` | HTMX search-results fragment |
| `GET` | `/locations/regions.geojson` | Authority boundary FeatureCollection |
| `GET` | `/locations/settlements.geojson` | City/town FeatureCollection |
| `GET` | `/locations/regions/<code>/panel/` | Selected-authority HTMX panel |
| `GET` | `/weather/regions/<code>/current/` | Weather HTMX fragment |
| `GET` | `/weather/<location>/` | Early placeholder detail page |

### Region GeoJSON parameters

`GET /locations/regions.geojson`

| Parameter | Required | Description |
| --- | --- | --- |
| `bbox` | No | `west,south,east,north` in longitude/latitude |
| `tolerance` | No | Simplification tolerance from `0` to `0.1`; default `0.001` |

Example:

```text
/locations/regions.geojson?bbox=-6,49,-1,56&tolerance=0.002
```

The query filters polygons that intersect the box and applies
`ST_SimplifyPreserveTopology` before serializing GeoJSON at six-decimal
precision. Invalid parameters return JSON with HTTP `400`.

### Settlement GeoJSON parameters

`GET /locations/settlements.geojson`

| Parameter | Required | Description |
| --- | --- | --- |
| `bbox` | No | `west,south,east,north` in longitude/latitude |
| `zoom` | No | Map zoom from `0` to `24` |

Example:

```text
/locations/settlements.geojson?bbox=-4,50,-1,53&zoom=7
```

When `zoom` is below `5.5`, the server returns cities only. At `5.5` or above,
it returns cities and towns. Each feature includes the preferred and alternate
name, settlement type, optional population, and associated authority code/name.

### Search parameters

`GET /locations/search/?query=Edinburgh`

Search is currently authority-only. Queries must contain between 2 and 120
characters after validation. Exact matches rank before prefix matches, which
rank before other case-insensitive partial matches.

## Weather integration

The application requests forecasts from:

```text
https://api.open-meteo.com/v1/forecast
```

No API key or application secret is required. The request uses:

- Model: `ukmo_seamless`
- Timezone: `Europe/London`
- Wind speed: miles per hour
- Current conditions: temperature, apparent temperature, humidity,
  precipitation, WMO code, cloud cover, wind speed/direction/gusts, and day/night
- Hourly forecast: 24 periods
- Daily forecast: 7 periods, including high/low temperature, rainfall total,
  wind, sunrise, sunset, and daylight duration

The provider SDK returns arrays whose order must match the requested variable
order. `apps/weather/services/transformers.py` centralizes that mapping and
normalizes provider data into typed application objects before templates see
it. It also rejects missing variables, non-finite values, empty forecasts, and
inconsistent array lengths.

Open-Meteo responses are cached locally for one hour using `requests-cache`.
Failed provider calls are retried five times with a short backoff, and calls
time out after ten seconds. Cache files begin with `.openmeteo-cache` and are
ignored by Git.

To force a fresh request while debugging, stop Django and remove only the
project's `.openmeteo-cache*` files, then restart the server.

Weather icons are local SVG symbols in `static/icons/weather.svg`; templates use
the normalized icon name rather than depending on remote icon assets.

## Testing and quality checks

The test suite uses pytest and pytest-django. `DJANGO_SETTINGS_MODULE` is set in
`pyproject.toml`, so use `pytest` rather than manually configuring Django.

Run all tests:

```bash
pytest
```

Run focused suites:

```bash
pytest apps/locations/tests
pytest apps/weather/tests
pytest tests/test_home.py
```

Run a single test with verbose output:

```bash
pytest apps/locations/tests/test_views.py -vv
```

Useful Django checks:

```bash
python3 manage.py check
python3 manage.py makemigrations --check --dry-run
```

Run Ruff:

```bash
ruff check .
```

At the current project baseline, the full Ruff command reports `RUF012` for
Django `Meta`/migration class attributes and `SIM117` in two constraint tests.
Those warnings do not affect runtime behaviour, but the command will return a
non-zero status until the lint policy or the flagged code is updated.

Verify the production-form frontend bundle can be generated:

```bash
npm run build
```

The tests cover models and constraints, boundary and settlement importers,
GeoJSON validation/filtering, search and HTMX views, Open-Meteo request
construction, response transformations, icon mapping, error handling, and
project smoke behaviour.

### Test database requirements

Django creates a separate test database. The configured database account must
be able to create/drop that database, and PostGIS must be available in the test
database. If a hosted provider restricts database creation, use a dedicated
PostGIS test database or suitable provider-specific test configuration rather
than running tests against valuable application data.

## Troubleshooting

### `Requested setting INSTALLED_APPS, but settings are not configured`

Install and invoke pytest through the active virtual environment:

```bash
pip install -r requirements.txt
pytest
```

The `pytest-django` plugin reads `DJANGO_SETTINGS_MODULE = "config.settings"`
from `pyproject.toml`. An `Unknown config option: DJANGO_SETTINGS_MODULE`
warning usually means `pytest-django` is missing from the active environment.

### `Could not find the GDAL library`

Install native GDAL/GEOS/PROJ packages, then verify that the loader sees GDAL:

```bash
gdalinfo --version
ldconfig -p | rg libgdal
```

Restart the virtual environment and rerun:

```bash
python3 manage.py check
```

If GDAL is installed in a non-standard path, locate the exact shared library
and set Django's `GDAL_LIBRARY_PATH` in `config/settings.py` as a last resort.
The value must be the shared-library file, not the `gdalinfo` executable.

### `python manage.py dbshell` cannot find `psql`

Install the PostgreSQL client tools. On Ubuntu/Debian:

```bash
sudo apt install postgresql-client
```

`dbshell` invokes the native `psql` executable; `psycopg2` alone does not
provide it.

### `DATABASE_URL` is missing

Ensure `.env` is in the same directory as `manage.py`, uses the exact variable
name, and contains no spaces around `=`:

```dotenv
DATABASE_URL=postgresql://USER:PASSWORD@HOST:PORT/DATABASE_NAME
```

### PostGIS types or extension are unavailable

Confirm that the URL points to the intended database and run:

```sql
SELECT PostGIS_Version();
```

If the function does not exist, PostGIS is not enabled for that database. The
plain PostgreSQL image in the current Compose file is not enough.

### Migrations report missing tables or relations

Run:

```bash
python3 manage.py migrate
python3 manage.py showmigrations locations
```

### The map area is blank

1. Run `npm run build` and reload without the browser cache.
2. Open the browser console and network panel for JavaScript or GeoJSON errors.
3. Confirm `/locations/regions.geojson` returns a FeatureCollection.
4. Confirm the browser can reach the current MapLibre demonstration style.
5. Confirm `static/js/maplibre-gl-worker.mjs` returns HTTP `200`.

### The basemap appears but authority polygons do not

Check whether regions exist:

```bash
python3 manage.py shell -c "from apps.locations.models import Region; print(Region.objects.count())"
```

If the count is zero, run the boundary import. If it is nonzero, inspect the
GeoJSON endpoint and browser console.

### City or town points do not appear

Check whether settlements exist:

```bash
python3 manage.py shell -c "from apps.locations.models import Settlement; print(Settlement.objects.count())"
```

Remember that towns are excluded below zoom `5.5`, and town labels do not appear
until zoom `7`. Also inspect `/locations/settlements.geojson` with a visible
bounding box.

### Settlements appear in the wrong place

Use the current importer, which reads the actual GeoPackage geometry and
transforms it from EPSG:27700 to EPSG:4326. Re-run the idempotent import to
update existing rows. Do not derive points from GeoPackage envelope/minimum
bounding rectangle values.

### A settlement does not select an authority

Inspect the import summary for records reported “without an authority.” Ensure
local-authority boundaries were imported before settlements and cover the point.
The `region` relationship is nullable to make unmatched source data visible
rather than silently discarding it.

### Weather fails to load

1. Confirm the Django process has internet access.
2. Open the browser network panel and inspect the weather fragment response.
3. Check the Django log for the authority code and provider error.
4. Confirm the authority has a valid `forecast_point`.
5. Remove the project `.openmeteo-cache*` files if testing a stale cached call.

Upstream failure renders an error fragment with a retry control rather than
breaking the map page.

### Tests cannot create the database

The database user needs test-database permissions, and the resulting database
needs PostGIS. Do not grant broad production permissions simply to make local
tests pass; use a dedicated development/test PostGIS instance instead.

## Data sources and attribution

This repository contains import code, not the full external geospatial source
datasets.

- **Authority boundaries:** the importer is source-agnostic, but the current
  project data uses a Counties and Unitary Authorities boundary release with
  official geography codes and names. Record the precise publisher, release,
  and licence alongside any deployed dataset.
- **Settlements:** [OS Open Names](https://www.ordnancesurvey.co.uk/products/os-open-names),
  supplied under Ordnance Survey's applicable OpenData terms. Preserve required
  Crown copyright/database-right attribution.
- **Weather:** [Open-Meteo](https://open-meteo.com/) using the UKMO seamless
  model. Follow Open-Meteo's current attribution and usage terms in deployments.
- **Basemap:** the application currently uses MapLibre's public demonstration
  style. It is suitable for development, not a production tile-service plan.

Always review the current licence and attribution requirements for the exact
release and service you use. The external datasets and weather responses are
not relicensed by this repository's GPL licence.

## Current limitations and roadmap

- Region search does not yet search settlements.
- `SavedLocation` exists at model/admin level but has no user-facing save flow.
- Authentication and personal dashboards are not yet part of the frontend.
- OS Open Names provides Great Britain settlement coverage; Northern Ireland
  needs a separate source.
- Settlement `population` is nullable and is not populated by the current
  importer, so dot size currently reflects city/town type rather than population.
- The `/weather/<location>/` route is an early placeholder; the interactive
  authority panel is the main forecast UI.
- The public MapLibre demonstration style should be replaced before deployment.
- The current settings are a single development settings module.
- Background refresh jobs, persistent forecast storage, observability, and
  application-level rate limiting are not yet implemented.

Likely next steps:

1. Add settlement-aware autocomplete while preserving authority-based weather.
2. Add clustering or collision rules for dense city/town areas.
3. Implement saved-location actions and authentication UI.
4. Add a dedicated production settings module and static-file strategy.
5. Replace the demonstration basemap with a properly licensed production style
   and tile provider.
6. Add deployment, monitoring, and continuous-integration configuration.

## Production considerations

The present `config/settings.py` is development-only:

- `DEBUG` is `True`.
- `SECRET_KEY` is a placeholder string.
- `ALLOWED_HOSTS` is empty.
- There is no separate production settings module.
- Production static-file serving has not been configured.
- Security headers, trusted origins, proxy/TLS settings, logging, and error
  monitoring need explicit production configuration.

Before deployment:

1. Load a strong secret key and all credentials from environment variables.
2. Disable debug mode.
3. Configure hosts, CSRF trusted origins, HTTPS, secure cookies, and proxy
   headers for the deployment platform.
4. Configure `STATIC_ROOT`, `collectstatic`, and an appropriate static-file or
   CDN strategy.
5. Use a managed PostGIS database with backups and least-privilege credentials.
6. Replace the demonstration basemap and document every data-provider licence.
7. Add timeouts, logging, monitoring, and rate controls appropriate to expected
   traffic.
8. Run tests, Django deployment checks, and the frontend build in CI.

Useful final check once production settings exist:

```bash
python3 manage.py check --deploy
```

## Command reference

```bash
# Activate local environment
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
npm ci

# Database
python3 manage.py migrate
python3 manage.py dbshell
python3 manage.py createsuperuser

# Geospatial imports
python3 manage.py import_regions --help
python3 manage.py import_settlements --help

# Development
npm run build
python3 manage.py runserver
npm run css:watch
npm run ts:watch

# Verification
pytest
ruff check .
python3 manage.py check
python3 manage.py makemigrations --check --dry-run
```

## Licence

The application source is licensed under the
[GNU General Public License, version 3](LICENSE). External datasets, map tiles,
and weather data remain subject to their respective providers' licences and
terms.
