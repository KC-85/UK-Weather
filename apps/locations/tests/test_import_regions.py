import json
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.locations.models import Region


def write_geojson(path, *, name="City of Edinburgh", geometry_type="Polygon"):
    if geometry_type == "Polygon":
        coordinates = [
            [
                [-3.30, 55.90],
                [-3.05, 55.90],
                [-3.05, 56.05],
                [-3.30, 56.05],
                [-3.30, 55.90],
            ]
        ]
    else:
        coordinates = [-3.1883, 55.9533]

    data = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "LAD25CD": "S12000036",
                    "LAD25NM": name,
                },
                "geometry": {
                    "type": geometry_type,
                    "coordinates": coordinates,
                },
            }
        ],
    }
    path.write_text(json.dumps(data), encoding="utf-8")


@pytest.mark.django_db
def test_import_regions_creates_region(tmp_path):
    source = tmp_path / "regions.geojson"
    output = StringIO()
    write_geojson(source)

    call_command(
        "import_regions",
        source,
        code_field="LAD25CD",
        name_field="LAD25NM",
        region_type=Region.Types.LOCAL_AUTHORITY,
        stdout=output,
    )

    region = Region.objects.get(code="S12000036")
    assert region.name == "City of Edinburgh"
    assert region.boundary.geom_type == "MultiPolygon"
    assert region.boundary.covers(region.forecast_point)
    assert "1 created, 0 updated" in output.getvalue()


@pytest.mark.django_db
def test_import_regions_updates_existing_region(tmp_path):
    source = tmp_path / "regions.geojson"
    write_geojson(source)
    command_options = {
        "code_field": "LAD25CD",
        "name_field": "LAD25NM",
        "region_type": Region.Types.LOCAL_AUTHORITY,
        "stdout": StringIO(),
    }
    call_command("import_regions", source, **command_options)
    write_geojson(source, name="Edinburgh")

    output = StringIO()
    command_options["stdout"] = output
    call_command("import_regions", source, **command_options)

    assert Region.objects.count() == 1
    assert Region.objects.get(code="S12000036").name == "Edinburgh"
    assert "0 created, 1 updated" in output.getvalue()


@pytest.mark.django_db
def test_import_regions_rejects_non_polygon_geometry(tmp_path):
    source = tmp_path / "regions.geojson"
    write_geojson(source, geometry_type="Point")

    with pytest.raises(CommandError, match="expected Polygon or MultiPolygon"):
        call_command(
            "import_regions",
            source,
            code_field="LAD25CD",
            name_field="LAD25NM",
            region_type=Region.Types.LOCAL_AUTHORITY,
        )
