import pytest
from django.contrib.gis.geos import MultiPolygon, Point, Polygon
from django.urls import reverse

from apps.locations.models import Region


@pytest.fixture
def region(db):
    boundary = MultiPolygon(
        Polygon(
            (
                (-3.30, 55.90),
                (-3.25, 55.9001),
                (-3.20, 55.8999),
                (-3.05, 55.90),
                (-3.05, 56.05),
                (-3.30, 56.05),
                (-3.30, 55.90),
            )
        ),
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
def test_regions_geojson_returns_feature_collection(client, region):
    response = client.get(reverse("locations:regions_geojson"))

    assert response.status_code == 200
    assert response["Content-Type"] == "application/geo+json"

    data = response.json()
    assert data["type"] == "FeatureCollection"
    assert len(data["features"]) == 1


@pytest.mark.django_db
def test_regions_geojson_includes_region_properties(client, region):
    response = client.get(reverse("locations:regions_geojson"))

    feature = response.json()["features"][0]
    assert feature["id"] == region.pk
    assert feature["properties"] == {
        "code": "S12000036",
        "name": "City of Edinburgh",
        "region_type": Region.Types.LOCAL_AUTHORITY,
    }


@pytest.mark.django_db
def test_regions_geojson_uses_polygonal_boundary_as_geometry(client, region):
    response = client.get(reverse("locations:regions_geojson"))

    geometry = response.json()["features"][0]["geometry"]
    assert geometry["type"] in {"Polygon", "MultiPolygon"}
    assert geometry["coordinates"]


@pytest.mark.django_db
def test_regions_geojson_filters_by_bounding_box(client, region):
    response = client.get(
        reverse("locations:regions_geojson"),
        {"bbox": "-3.4,55.8,-3.0,56.1"},
    )

    assert [feature["id"] for feature in response.json()["features"]] == [
        region.pk
    ]


@pytest.mark.django_db
def test_regions_geojson_excludes_regions_outside_bounding_box(client, region):
    response = client.get(
        reverse("locations:regions_geojson"),
        {"bbox": "-0.5,51.2,0.2,51.7"},
    )

    assert response.json()["features"] == []


@pytest.mark.django_db
def test_regions_geojson_simplifies_geometry(client, region):
    response = client.get(
        reverse("locations:regions_geojson"),
        {"tolerance": "0.001"},
    )

    returned_ring = response.json()["features"][0]["geometry"]["coordinates"][0][0]
    stored_ring = region.boundary.coords[0][0]
    assert len(returned_ring) < len(stored_ring)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "bbox",
    [
        "-3.4,55.8,-3.0",
        "west,55.8,-3.0,56.1",
        "-3.0,55.8,-3.4,56.1",
        "-3.4,56.1,-3.0,55.8",
        "-181,55.8,-3.0,56.1",
    ],
)
def test_regions_geojson_rejects_invalid_bounding_box(client, bbox):
    response = client.get(
        reverse("locations:regions_geojson"),
        {"bbox": bbox},
    )

    assert response.status_code == 400
    assert "error" in response.json()


@pytest.mark.django_db
@pytest.mark.parametrize("tolerance", ["invalid", "-0.001", "0.101"])
def test_regions_geojson_rejects_invalid_tolerance(client, tolerance):
    response = client.get(
        reverse("locations:regions_geojson"),
        {"tolerance": tolerance},
    )

    assert response.status_code == 400
    assert "error" in response.json()


@pytest.mark.django_db
def test_regions_geojson_returns_empty_feature_collection(client):
    response = client.get(reverse("locations:regions_geojson"))

    assert response.status_code == 200
    assert response.json()["features"] == []


@pytest.mark.django_db
def test_region_panel_returns_selected_region(client, region):
    response = client.get(
        reverse("locations:region_panel", args=[region.code])
    )

    assert response.status_code == 200
    assert "locations/partials/region_panel.html" in [
        template.name for template in response.templates
    ]
    assert response.context["region"] == region
    assert b"City of Edinburgh" in response.content
    assert b"Local Authority" in response.content


@pytest.mark.django_db
def test_region_panel_includes_forecast_coordinates(client, region):
    response = client.get(
        reverse("locations:region_panel", args=[region.code])
    )

    assert b"55.9533" in response.content
    assert b"-3.1883" in response.content


@pytest.mark.django_db
def test_region_panel_loads_current_weather_with_htmx(client, region):
    response = client.get(
        reverse("locations:region_panel", args=[region.code])
    )

    weather_url = reverse(
        "weather:current_conditions",
        args=[region.code],
    )
    assert weather_url.encode() in response.content
    assert b'hx-trigger="load"' in response.content
    assert b'id="current-weather"' in response.content
    assert b"Updating forecast" in response.content


@pytest.mark.django_db
def test_region_panel_returns_not_found_for_unknown_code(client):
    response = client.get(
        reverse("locations:region_panel", args=["UNKNOWN"])
    )

    assert response.status_code == 404
