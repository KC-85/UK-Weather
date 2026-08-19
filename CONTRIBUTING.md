# Contributing to UK Weather

Thank you for considering a contribution to UK Weather. Contributions of all
sizes are welcome, including bug reports, documentation improvements, tests,
accessibility fixes, new map interactions, and weather or geospatial features.

This guide explains how to work on the project safely and consistently. The
[README](README.md) contains the full application architecture, installation
guide, data-import instructions, endpoint reference, and troubleshooting notes.

## Contents

- [Ways to contribute](#ways-to-contribute)
- [Before starting](#before-starting)
- [Development setup](#development-setup)
- [Contribution workflow](#contribution-workflow)
- [Project principles](#project-principles)
- [Coding guidelines](#coding-guidelines)
- [Database and model changes](#database-and-model-changes)
- [Geospatial and data-import changes](#geospatial-and-data-import-changes)
- [Weather integration changes](#weather-integration-changes)
- [Frontend changes](#frontend-changes)
- [Testing](#testing)
- [Documentation](#documentation)
- [Submitting a change](#submitting-a-change)
- [Bug reports and feature requests](#bug-reports-and-feature-requests)
- [Security and sensitive information](#security-and-sensitive-information)
- [Data licensing and attribution](#data-licensing-and-attribution)
- [Definition of done](#definition-of-done)

## Ways to contribute

Useful contributions include:

- Reproducing and fixing bugs.
- Adding or strengthening automated tests.
- Improving keyboard navigation, screen-reader output, colour contrast, or
  loading/error feedback.
- Improving local-authority or settlement map performance.
- Adding settlement-aware search while keeping forecasts authority-based.
- Improving weather presentation or provider error handling.
- Improving GeoDjango queries and spatial-data validation.
- Supporting an appropriate settlement source for Northern Ireland.
- Improving setup, deployment, data-attribution, or troubleshooting
  documentation.
- Reviewing code and providing focused, constructive feedback.

Small, focused changes are generally easier to understand, review, test, and
merge than a single contribution containing several unrelated features.

## Before starting

For a typo, test improvement, or small self-contained bug fix, it is normally
fine to begin directly.

For a larger feature, schema change, new dependency, new external API, or new
geospatial dataset, discuss the intended approach in an issue first. This helps
confirm that the proposal fits the architecture before substantial work begins.

Before coding:

1. Read the [README](README.md), particularly the architecture, data model,
   setup, testing, and current limitations sections.
2. Check existing issues and pull requests to avoid duplicating active work.
3. Confirm that you can run the existing application and relevant tests.
4. Identify whether your change requires PostGIS, a source dataset, internet
   access, or frontend compilation.
5. Keep external data files, credentials, caches, and virtual environments out
   of Git.

## Development setup

The project uses a normal Python virtual environment and `pip`. It does not use
`uv`.

```bash
python3 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
npm ci
```

Create a root `.env` containing a PostGIS-capable database URL:

```dotenv
DATABASE_URL=postgresql://USER:PASSWORD@HOST:PORT/DATABASE_NAME
```

Then prepare the project:

```bash
python manage.py migrate
npm run build
python manage.py check
python manage.py runserver
```

The current `compose.yml` uses standard PostgreSQL rather than a
PostGIS-enabled image. Do not assume that running it as written provides the
spatial types required by GeoDjango. See the README for database options and
native GDAL/GEOS/PROJ prerequisites.

Authority boundaries and OS Open Names are external datasets and are not stored
in this repository. Most application tests create their own minimal geometries,
so the complete datasets are not required for ordinary test development.

## Contribution workflow

The exact Git hosting workflow may vary, but the recommended process is:

1. Fork the repository when you do not have write access.
2. Synchronize your default branch with the upstream repository.
3. Create a focused branch from the latest default branch.
4. Make the smallest coherent change that solves the problem.
5. Add or update tests and documentation.
6. Run the checks relevant to the change.
7. Review the final diff for secrets, generated noise, and unrelated edits.
8. Commit with a clear message and open a pull request.

Example branch names:

```text
feature/settlement-search
fix/region-tooltip-position
docs/postgis-setup
test/weather-timeout
```

Avoid mixing formatting-only changes, dependency upgrades, generated data, and
feature work in one contribution unless they are inseparable.

Do not rewrite or remove another contributor's unrelated work to make your
change easier to apply. If your branch has a conflict, resolve only the lines
necessary for your contribution and call out any important resolution in the
pull request.

## Project principles

New work should preserve these architectural decisions unless an agreed design
change says otherwise.

### Weather belongs to authorities

Local-authority polygons are the selectable forecast areas. Cities and towns
are contextual map points. Clicking a settlement selects its associated
authority and requests weather using that authority's `forecast_point`.

Do not silently change settlement clicks to make settlement-coordinate weather
requests. Such a change would create inconsistent forecast semantics across the
interface.

### Spatial work happens in PostGIS

Use GeoDjango/PostGIS for spatial filtering, coverage, transformations, and
simplification rather than loading an entire national dataset into Python or
the browser. Map endpoints must remain bounding-box aware.

### Provider data is normalized before rendering

Templates should receive application-owned forecast objects, not raw
Open-Meteo SDK arrays. Provider-specific ordering and validation belong in the
weather service and transformer layers.

### HTML is the primary UI response

HTMX endpoints return small server-rendered template fragments for search and
weather panels. TypeScript coordinates map interactions, request state, and
browser events; it should not duplicate server-side domain logic.

### The interface must fail clearly

Network requests and external data can fail. User-visible interactions should
include appropriate loading, empty, error, and retry states. Exceptions should
be handled at a layer that can add useful context without hiding programming
errors.

## Coding guidelines

### Python and Django

- Target Python 3.12 or newer.
- Follow the existing Django application boundaries: `core`, `locations`, and
  `weather`.
- Use four spaces and keep lines within the configured Ruff limit of 88
  characters where practical.
- Prefer descriptive names and small functions with a single responsibility.
- Keep views thin; move provider, transformation, or import logic into an
  appropriate service or command helper.
- Use Django forms or explicit parsing helpers to validate user input.
- Restrict view methods with decorators such as `@require_GET` when applicable.
- Avoid catching broad `Exception` unless it is re-raised or there is a
  carefully justified boundary-level fallback.
- Log useful operational context, but never credentials, full database URLs,
  or personal information.
- Use Django's URL reversing in Python and templates rather than hard-coded
  internal paths.
- Preserve type hints in service and transformation code.
- Keep admin changes practical for inspecting and maintaining project data.

### Templates and HTMX

- Put reusable global fragments in `templates/components/`.
- Put application-specific partials under that application's template
  namespace.
- Return fragments, not complete pages, from HTMX-only endpoints.
- Preserve semantic HTML, labels, focus behaviour, and accessible names.
- Use `aria-live`, `aria-busy`, status text, and retry controls where a request
  changes content asynchronously.
- Do not make essential information available only on pointer hover.
- Escape untrusted values through Django's normal template auto-escaping.

### TypeScript

- Edit source files in `assets/ts/`, not the bundled files in `static/js/`.
- Keep DOM queries typed and handle missing elements safely.
- Prefer application events for communication between the map and HTMX UI over
  tightly coupling unrelated components.
- Abort stale bounding-box requests when newer map movement makes them
  irrelevant.
- Validate `dataset` and GeoJSON property values before using them.
- Avoid adding `any`; create a focused type for browser or response data.
- Do not expose secrets in browser code. Open-Meteo does not require an API key.

### CSS and Tailwind

- Edit `assets/css/input.css` and template utility classes.
- Do not manually edit `static/css/output.css`; it is generated and ignored by
  Git.
- Preserve responsive behaviour and visible keyboard focus states.
- Check changes at narrow and wide viewport sizes.
- Do not rely on colour alone to communicate selection, status, or errors.

### Dependencies

Add a dependency only when it provides clear value that is difficult to achieve
with the existing stack.

When adding or updating a dependency:

- Explain the reason and alternatives considered in the pull request.
- Update `requirements.txt` or both `package.json` and `package-lock.json` as
  appropriate.
- Check compatibility with the project's supported Python and Node tooling.
- Review its licence, maintenance status, and browser/server bundle impact.
- Keep dependency-only changes separate from unrelated features where possible.

## Database and model changes

Every model change must include a Django migration.

```bash
python manage.py makemigrations
python manage.py migrate
python manage.py makemigrations --check --dry-run
```

Review generated migrations before committing them. Check field defaults,
nullability, indexes, constraints, deletion behaviour, and whether an operation
could lock or rewrite a large table.

For spatial fields:

- State and preserve the expected SRID.
- Use `PointField` for settlement/forecast points and `MultiPolygonField` for
  region boundaries unless the data model intentionally changes.
- Add database indexes or constraints based on demonstrated query needs.
- Test geometry type, empty geometry, invalid geometry, and transformations.
- Avoid irreversible data migrations without a documented recovery strategy.

Never develop or test destructive migrations against a valuable shared
database. Use a dedicated development/test PostGIS database with backups where
appropriate.

## Geospatial and data-import changes

Geospatial source files can be extremely large, and source formats are not
always as straightforward as their visible columns suggest.

When changing an importer:

- Inspect the source layer, fields, CRS, and geometry with GDAL tools first.
- Read the actual geometry payload; do not substitute an envelope or bounding
  rectangle for a point or polygon.
- Validate required tables, fields, geometry type, SRID, empty geometry, and
  malformed records.
- Transform stored geometry to SRID 4326.
- Make repeat imports idempotent through stable official/source identifiers.
- Wrap related writes in a transaction where memory and data volume permit.
- Use bulk database operations for large record sets.
- Report created, updated, skipped, invalid, and unmatched counts clearly.
- Provide `--limit` and/or `--dry-run` behaviour for safe verification when
  appropriate.
- Test bilingual naming and source-specific edge cases.
- Avoid reading millions of irrelevant source records into memory.

Do not commit GeoPackages, national GeoJSON files, source ZIP archives, database
dumps, or generated bulk fixtures. Instead, document where the data comes from
and construct small synthetic geometries in tests.

If a change affects point-to-authority assignment, test points:

- Clearly inside a polygon.
- Outside every polygon.
- Near a boundary.
- In a polygon with multiple parts when relevant.

Import authority boundaries before settlements when manually testing the full
pipeline.

## Weather integration changes

The current provider is Open-Meteo using `ukmo_seamless`, with no API key.

When adding or reordering requested variables:

1. Update the ordered variable constants in
   `apps/weather/services/client.py`.
2. Update the associated name-to-index transformation logic.
3. Update the application forecast dataclasses if the normalized domain data
   changes.
4. Add client request tests and transformer success/error tests.
5. Update templates and this documentation where the UI changes.

The order of Open-Meteo SDK variables is significant. Never assume a returned
array can be identified without matching it to the request order.

Tests must mock or fake the provider response. They should not make real
Open-Meteo network calls: live forecasts change, upstream availability is
outside the test's control, and repeated calls are unfriendly to the service.

Convert provider errors into the application's `WeatherServiceError` at the
integration boundary, and preserve the existing user-facing retry experience.
Validate missing, empty, inconsistent, and non-finite response data.

## Frontend changes

Build frontend assets after editing TypeScript, Tailwind source, icons, or npm
dependencies:

```bash
npm run build
```

For interactive development:

```bash
npm run css:watch
npm run ts:watch
```

The following outputs are generated:

- `static/css/output.css` is ignored and should not be committed.
- `static/js/app.js` and `static/js/app.js.map` are tracked build output.
- MapLibre's shared and worker modules under `static/js/` are copied from the
  installed npm package and are tracked.

When TypeScript or MapLibre dependencies change, regenerate the assets and
include the relevant tracked output so a checkout remains runnable. Do not edit
the generated files directly.

For map changes, manually verify:

- Initial UK view and basemap loading.
- Region and settlement bounding-box refreshes.
- Rapid panning/zooming and stale-request cancellation.
- Hover tooltip behaviour.
- Mouse and keyboard-accessible selection paths where provided.
- Search selection and map fitting.
- City/town visibility at their zoom thresholds.
- Loading, success, error, and retry panel states.
- Narrow and wide screen layouts.

Keep GeoJSON responses bounded. A national unsimplified authority payload or
all settlement points should not be fetched on every map movement.

## Testing

New behaviour and bug fixes should include tests at the lowest useful level.
A bug fix should ideally include a regression test that fails without the fix.

Run the complete suite:

```bash
pytest
```

Focused examples:

```bash
pytest apps/locations/tests
pytest apps/weather/tests
pytest apps/locations/tests/test_views.py -vv
```

Also run:

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
npm run build
ruff check .
```

The current full Ruff baseline reports known `RUF012` findings for Django
`Meta`/migration class attributes and two `SIM117` findings in constraint tests.
Do not introduce additional lint errors. If a contribution addresses the
baseline, keep those mechanical fixes clearly separated from feature work.

### Test design

- Use pytest and pytest-django conventions already present in the repository.
- Name files `test_*.py` and tests after observable behaviour.
- Prefer small fixtures/factories over large serialized datasets.
- Test success, validation failure, not-found, and upstream-error paths.
- Assert response status, content type, important content, and database effects.
- For GeoJSON, assert geometry and properties as well as feature counts.
- Use realistic SRIDs and simple synthetic points/polygons in spatial tests.
- Avoid ordering assumptions unless ordering is part of the contract.
- Mock external weather calls at the narrowest stable boundary.

### Test database safety

pytest-django creates a separate test database. The configured database account
must be able to create/drop it, and PostGIS must be available to that database.
Never make a production database masquerade as the test database or bypass
Django's test-database safeguards.

If your provider does not permit test database creation, configure a dedicated
local or hosted PostGIS test instance before running database-backed tests.

## Documentation

Update documentation whenever a contribution changes:

- Required software or environment variables.
- Setup, migration, import, or build commands.
- Routes, query parameters, or response properties.
- User-visible map or weather behaviour.
- Data sources, licences, or attribution.
- Known limitations or production requirements.

Commands in documentation should be safe to copy, use repository-relative or
clearly placeholder paths, and avoid personal usernames, credentials, or
machine-specific locations.

Add docstrings and comments where they explain a non-obvious reason, invariant,
source-format rule, or external protocol. Avoid comments that merely repeat the
code.

## Submitting a change

### Commits

Use short, imperative commit subjects that explain the outcome:

```text
Add settlement results to region search
Fix GeoPackage point geometry decoding
Document local PostGIS requirements
```

There is no requirement to use Conventional Commits. Prefer a small number of
coherent commits over one commit per edit or a single commit containing
unrelated work.

Do not commit:

- `.env` or credentials.
- Virtual environments or `node_modules`.
- Open-Meteo caches.
- Full external GIS datasets or database dumps.
- Editor/operating-system files.
- Debug output or temporary scripts unrelated to the change.

### Pull requests

A good pull request includes:

- A concise explanation of the problem and the chosen solution.
- The issue it closes or relates to, when one exists.
- Important architecture, performance, or data-licensing decisions.
- Migration and data-import instructions when applicable.
- Tests added and the exact checks run.
- Screenshots or a short recording for visible UI/map changes.
- Accessibility checks performed for interactive changes.
- Known limitations or follow-up work.

Suggested description:

```markdown
## What changed

Describe the user-visible and technical outcome.

## Why

Explain the problem and key decisions.

## Verification

- [ ] `pytest`
- [ ] `python manage.py check`
- [ ] `python manage.py makemigrations --check --dry-run`
- [ ] `npm run build` (when frontend files are affected)
- [ ] Manual map/weather checks (when UI behaviour is affected)

## Data or migration notes

Describe schema, import, source-data, licence, or deployment implications.

## Screenshots

Add before/after images for visual changes.
```

Before submitting, inspect:

```bash
git status --short
git diff --check
git diff
```

Ensure the diff contains only intentional work and does not reveal secrets or
personal filesystem paths.

## Bug reports and feature requests

Search existing issues first. When opening a bug report, include:

- A clear title and expected behaviour.
- What actually happened.
- Minimal reproduction steps.
- Relevant Python, Django, browser, PostgreSQL/PostGIS, GDAL, and Node versions.
- The affected endpoint, authority code, zoom, or bounding box when relevant.
- A sanitized traceback, Django log excerpt, or browser-console error.
- Whether `python manage.py check`, `pytest`, and `npm run build` succeed.
- Screenshots for visual problems.

Never include `.env`, database credentials, session cookies, private URLs, or
unredacted provider account information.

For feature requests, describe the user problem before prescribing an
implementation. Explain how the proposal interacts with authority-based
weather, map performance, accessibility, and data licensing where relevant.

## Security and sensitive information

Do not publish an actively exploitable vulnerability, credential, or private
database URL in a public issue. Contact the repository owner through an
available private channel on the hosting platform and provide:

- The affected component and version/commit.
- Reproduction details with sensitive values removed.
- The realistic impact.
- Any suggested mitigation.

Do not access data, accounts, or infrastructure beyond what is necessary to
demonstrate the issue safely.

The following are always sensitive:

- `DATABASE_URL` values.
- Django secret keys.
- Authentication cookies or CSRF tokens.
- Hosted database/project identifiers when they grant or reveal access.
- User location or saved-location information.

## Data licensing and attribution

The repository's source code licence does not override the licences of imported
boundaries, OS Open Names, map styles/tiles, or weather data.

A contribution that adds or changes an external dataset or service must
document:

- Publisher and product name.
- Exact release/version where practical.
- Coverage and important omissions.
- Source coordinate reference system and geometry type.
- Licence and required attribution.
- Update frequency and a repeatable import/update process.
- Whether redistribution of the source or derived data is permitted.

Do not add a dataset merely because it is downloadable. Confirm that its terms
allow the intended storage, processing, display, and deployment.

OS Open Names attribution and any boundary-source attribution must remain
visible and accurate where required. A new basemap provider must be suitable for
the expected traffic; public demonstration tile services are not a production
capacity plan.

By contributing code to this repository, you agree that it may be distributed
under the project's [GNU General Public License version 3](LICENSE). You must
have the right to submit everything included in your contribution.

## Definition of done

A contribution is ready for review when:

- The change has one clear purpose and matches the agreed scope.
- The implementation follows the existing architecture or documents why it
  intentionally changes it.
- New behaviour and regressions are covered by appropriate tests.
- Relevant tests, Django checks, migration checks, and frontend builds pass.
- Spatial queries remain bounded and external calls are not made from tests.
- Loading, empty, error, and retry states are handled where relevant.
- Accessibility and responsive behaviour have been considered.
- Migrations and data-import implications are documented.
- Documentation, endpoint details, and attribution are current.
- Generated assets are refreshed when their sources change.
- The diff contains no credentials, personal paths, large datasets, caches, or
  unrelated changes.
- The pull-request description explains what changed and how it was verified.

Thank you for helping make UK Weather accurate, accessible, maintainable, and
useful.
