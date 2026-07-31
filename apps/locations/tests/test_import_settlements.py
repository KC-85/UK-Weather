import sqlite3
from io import StringIO

import pytest
from django.contrib.gis.geos import MultiPolygon, Point, Polygon
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.locations.models import Region, Settlement


def write_open_names_database(path, rows):
    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            CREATE TABLE named_place (
                id TEXT,
                name1 TEXT,
                name1_lang TEXT,
                name2 TEXT,
                name2_lang TEXT,
                type TEXT,
                local_type TEXT,
                mbr_xmin REAL,
                mbr_ymin REAL,
                country TEXT
            )
            """
        )
        connection.executemany(
            """
            INSERT INTO named_place VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )


@pytest.fixture
def authority(db):
    boundary = MultiPolygon(
        Polygon.from_bbox((-3.30, 55.90, -3.05, 56.05)),
        srid=4326,
    )
    return Region.objects.create(
        code="S12000036",
        name="City of Edinburgh",
        region_type=Region.Types.LOCAL_AUTHORITY,
        boundary=boundary,
        forecast_point=Point(-3.1883, 55.9533, srid=4326),
    )


@pytest.mark.django_db
def test_import_settlements_creates_cities_and_towns(
    tmp_path,
    authority,
):
    source = tmp_path / "opname.gpkg"
    output = StringIO()
    write_open_names_database(
        source,
        [
            (
                "os-city",
                "Edinburgh",
                "eng",
                None,
                None,
                "populatedPlace",
                "City",
                325897,
                674001,
                "Scotland",
            ),
            (
                "os-town",
                "Leith",
                "eng",
                None,
                None,
                "populatedPlace",
                "Town",
                327000,
                676000,
                "Scotland",
            ),
            (
                "os-village",
                "Test Village",
                "eng",
                None,
                None,
                "populatedPlace",
                "Village",
                325897,
                674001,
                "Scotland",
            ),
        ],
    )

    call_command("import_settlements", source, stdout=output)

    assert Settlement.objects.count() == 2
    edinburgh = Settlement.objects.get(source_id="os-city")
    assert edinburgh.name == "Edinburgh"
    assert edinburgh.settlement_type == Settlement.Types.CITY
    assert edinburgh.country == Settlement.Countries.SCOTLAND
    assert edinburgh.region == authority
    assert edinburgh.location.srid == 4326
    assert edinburgh.location.x == pytest.approx(-3.1883, abs=0.001)
    assert edinburgh.location.y == pytest.approx(55.9533, abs=0.001)
    assert "2 created, 0 updated; 0 without an authority" in output.getvalue()


@pytest.mark.django_db
def test_import_settlements_is_idempotent(tmp_path, authority):
    source = tmp_path / "opname.gpkg"
    row = (
        "os-city",
        "Edinburgh",
        "eng",
        None,
        None,
        "populatedPlace",
        "City",
        325897,
        674001,
        "Scotland",
    )
    write_open_names_database(source, [row])
    call_command("import_settlements", source, stdout=StringIO())

    with sqlite3.connect(source) as connection:
        connection.execute(
            "UPDATE named_place SET name1 = ? WHERE id = ?",
            ["Edinburgh City", "os-city"],
        )

    output = StringIO()
    call_command("import_settlements", source, stdout=output)

    assert Settlement.objects.count() == 1
    assert Settlement.objects.get().name == "Edinburgh City"
    assert "0 created, 1 updated" in output.getvalue()


@pytest.mark.django_db
def test_import_settlements_prefers_english_bilingual_name(tmp_path):
    source = tmp_path / "opname.gpkg"
    write_open_names_database(
        source,
        [
            (
                "os-swansea",
                "Abertawe",
                "cym",
                "Swansea",
                "eng",
                "populatedPlace",
                "City",
                259192,
                186966,
                "Wales",
            )
        ],
    )

    call_command("import_settlements", source, stdout=StringIO())

    settlement = Settlement.objects.get()
    assert settlement.name == "Swansea"
    assert settlement.alternate_name == "Abertawe"


@pytest.mark.django_db
def test_import_settlements_dry_run_does_not_write(tmp_path):
    source = tmp_path / "opname.gpkg"
    output = StringIO()
    write_open_names_database(
        source,
        [
            (
                "os-city",
                "Edinburgh",
                "eng",
                None,
                None,
                "populatedPlace",
                "City",
                325897,
                674001,
                "Scotland",
            )
        ],
    )

    call_command(
        "import_settlements",
        source,
        dry_run=True,
        stdout=output,
    )

    assert not Settlement.objects.exists()
    assert "Validated 1 settlements" in output.getvalue()
    assert "no data was written" in output.getvalue()


def test_import_settlements_rejects_invalid_schema(tmp_path):
    source = tmp_path / "invalid.gpkg"
    with sqlite3.connect(source) as connection:
        connection.execute("CREATE TABLE another_layer (id TEXT)")

    with pytest.raises(CommandError, match="named_place.*was not found"):
        call_command("import_settlements", source, dry_run=True)


def test_import_settlements_rejects_non_positive_limit(tmp_path):
    source = tmp_path / "opname.gpkg"
    source.touch()

    with pytest.raises(CommandError, match="limit must be a positive"):
        call_command("import_settlements", source, limit=0, dry_run=True)
