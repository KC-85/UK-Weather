import pytest
from django.contrib.gis.geos import MultiPolygon, Point, Polygon
from django.urls import reverse

from apps.locations.models import Region, Settlement


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


@pytest.fixture
def settlements(db, region):
    city = Settlement.objects.create(
        source=Settlement.Sources.OS_OPEN_NAMES,
        source_id="os-city",
        name="Edinburgh",
        settlement_type=Settlement.Types.CITY,
        country=Settlement.Countries.SCOTLAND,
        location=Point(-3.1883, 55.9533, srid=4326),
        region=region,
    )
    town = Settlement.objects.create(
        source=Settlement.Sources.OS_OPEN_NAMES,
        source_id="os-town",
        name="Leith",
        alternate_name="Lìte",
        settlement_type=Settlement.Types.TOWN,
        country=Settlement.Countries.SCOTLAND,
        location=Point(-3.10, 55.97, srid=4326),
        region=region,
    )
    village = Settlement.objects.create(
        source=Settlement.Sources.OS_OPEN_NAMES,
        source_id="os-village",
        name="Test Village",
        settlement_type=Settlement.Types.VILLAGE,
        country=Settlement.Countries.SCOTLAND,
        location=Point(-3.15, 55.96, srid=4326),
        region=region,
    )
    return city, town, village


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
def test_settlements_geojson_returns_cities_and_towns(
    client,
    settlements,
):
    response = client.get(reverse("locations:settlements_geojson"))

    assert response.status_code == 200
    assert response["Content-Type"] == "application/geo+json"
    data = response.json()
    assert data["type"] == "FeatureCollection"
    assert [feature["id"] for feature in data["features"]] == [
        "os-city",
        "os-town",
    ]


@pytest.mark.django_db
def test_settlements_geojson_includes_point_and_authority_properties(
    client,
    settlements,
    region,
):
    response = client.get(reverse("locations:settlements_geojson"))

    feature = response.json()["features"][1]
    assert feature["geometry"] == {
        "type": "Point",
        "coordinates": [-3.1, 55.97],
    }
    assert feature["properties"] == {
        "source_id": "os-town",
        "name": "Leith",
        "alternate_name": "Lìte",
        "settlement_type": Settlement.Types.TOWN,
        "population": None,
        "region_code": region.code,
        "region_name": region.name,
    }


@pytest.mark.django_db
def test_settlements_geojson_filters_by_bounding_box(client, settlements):
    response = client.get(
        reverse("locations:settlements_geojson"),
        {"bbox": "-3.20,55.94,-3.17,55.97"},
    )

    assert [
        feature["properties"]["name"]
        for feature in response.json()["features"]
    ] == ["Edinburgh"]


@pytest.mark.django_db
def test_settlements_geojson_hides_towns_at_national_zoom(
    client,
    settlements,
):
    response = client.get(
        reverse("locations:settlements_geojson"),
        {"zoom": "5"},
    )

    assert [
        feature["properties"]["settlement_type"]
        for feature in response.json()["features"]
    ] == [Settlement.Types.CITY]


@pytest.mark.django_db
def test_settlements_geojson_includes_towns_when_zoomed_in(
    client,
    settlements,
):
    response = client.get(
        reverse("locations:settlements_geojson"),
        {"zoom": "5.5"},
    )

    assert len(response.json()["features"]) == 2


@pytest.mark.django_db
@pytest.mark.parametrize("zoom", ["invalid", "nan", "-1", "25"])
def test_settlements_geojson_rejects_invalid_zoom(client, zoom):
    response = client.get(
        reverse("locations:settlements_geojson"),
        {"zoom": zoom},
    )

    assert response.status_code == 400
    assert "error" in response.json()


@pytest.mark.django_db
def test_settlements_geojson_rejects_invalid_bounding_box(client):
    response = client.get(
        reverse("locations:settlements_geojson"),
        {"bbox": "invalid"},
    )

    assert response.status_code == 400
    assert "error" in response.json()


def test_settlements_geojson_rejects_post(client):
    response = client.post(reverse("locations:settlements_geojson"))

    assert response.status_code == 405


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


@pytest.mark.django_db
def test_region_search_finds_regions_case_insensitively(client, region):
    response = client.get(
        reverse("locations:region_search"),
        {"query": "eDiNbUrGh"},
    )

    assert response.status_code == 200
    assert "locations/partials/search_results.html" in [
        template.name for template in response.templates
    ]
    assert list(response.context["regions"]) == [region]
    assert b"City of Edinburgh" in response.content
    assert b'data-region-code="S12000036"' in response.content
    assert b"data-region-bounds=" in response.content


@pytest.mark.django_db
def test_region_search_prioritizes_exact_then_prefix_matches(
    client,
    region,
):
    prefix_match = Region.objects.create(
        code="S12000999",
        name="City of Edinburgh North",
        region_type=Region.Types.LOCAL_AUTHORITY,
        boundary=region.boundary,
        forecast_point=Point(-3.18, 56.0, srid=4326),
    )

    response = client.get(
        reverse("locations:region_search"),
        {"query": "City of Edinburgh"},
    )

    assert list(response.context["regions"]) == [region, prefix_match]


@pytest.mark.django_db
def test_region_search_returns_empty_state(client):
    response = client.get(
        reverse("locations:region_search"),
        {"query": "Not a UK region"},
    )

    assert response.status_code == 200
    assert b"No regions found" in response.content


@pytest.mark.django_db
def test_region_search_requires_at_least_two_characters(client, region):
    response = client.get(
        reverse("locations:region_search"),
        {"query": "E"},
    )

    assert response.status_code == 200
    assert not response.context["form"].is_valid()
    assert b"at least 2 characters" in response.content
    assert b"City of Edinburgh" not in response.content


@pytest.mark.django_db
def test_region_search_limits_results(client, region):
    for index in range(10):
        Region.objects.create(
            code=f"S12001{index:03}",
            name=f"Test Region {index:02}",
            region_type=Region.Types.LOCAL_AUTHORITY,
            boundary=region.boundary,
            forecast_point=Point(-3.0 + (index / 100), 56.0, srid=4326),
        )

    response = client.get(
        reverse("locations:region_search"),
        {"query": "Test Region"},
    )

    assert len(response.context["regions"]) == 8
    assert response.content.count(b"data-region-search-result") == 8


def test_region_search_clears_results_for_blank_query(client):
    response = client.get(
        reverse("locations:region_search"),
        {"query": ""},
    )

    assert response.status_code == 200
    assert response.content.strip() == b""


def test_region_search_rejects_post(client):
    response = client.post(
        reverse("locations:region_search"),
        {"query": "Edinburgh"},
    )

    assert response.status_code == 405


def test_home_includes_region_search_controls(client):
    response = client.get(reverse("core:home"))

    assert response.status_code == 200
    assert reverse("locations:region_search").encode() in response.content
    assert b'id="region-search-input"' in response.content
    assert b'id="region-search-results"' in response.content
    assert b'id="region-search-error"' in response.content
    assert reverse("locations:settlements_geojson").encode() in response.content
