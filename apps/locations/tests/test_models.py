import pytest
from django.contrib.gis.geos import MultiPolygon, Point, Polygon
from django.db import IntegrityError, transaction

from apps.locations.models import Region, SavedLocation, Settlement


@pytest.fixture
def region(db):
    boundary = MultiPolygon(
        Polygon(
            (
                (-3.30, 55.90),
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
def test_region_string(region):
    assert str(region) == "City of Edinburgh"


@pytest.mark.django_db
def test_region_contains_point_inside_boundary(region):
    point = Point(-3.1883, 55.9533, srid=4326)

    matching_regions = Region.objects.filter(boundary__covers=point)

    assert list(matching_regions) == [region]


@pytest.mark.django_db
def test_region_does_not_contain_point_outside_boundary(region):
    point = Point(-4.2518, 55.8642, srid=4326)

    matching_regions = Region.objects.filter(boundary__covers=point)

    assert region not in matching_regions


@pytest.mark.django_db
def test_region_parent_child_relationship(region):
    nation = Region.objects.create(
        code="S92000003",
        name="Scotland",
        region_type=Region.Types.NATION,
        boundary=region.boundary,
        forecast_point=Point(-4.2026, 56.4907, srid=4326),
    )
    region.parent = nation
    region.save(update_fields=["parent"])

    assert region.parent == nation
    assert list(nation.children.all()) == [region]


@pytest.mark.django_db
def test_settlement_string_and_region_relationship(region):
    settlement = Settlement.objects.create(
        source=Settlement.Sources.OS_OPEN_NAMES,
        source_id="osgb4000000074565735",
        name="Edinburgh",
        settlement_type=Settlement.Types.CITY,
        country=Settlement.Countries.SCOTLAND,
        location=Point(-3.1883, 55.9533, srid=4326),
        region=region,
    )

    assert str(settlement) == "Edinburgh"
    assert list(region.settlements.all()) == [settlement]


@pytest.mark.django_db
def test_settlement_source_identifier_is_unique(region):
    values = {
        "source": Settlement.Sources.OS_OPEN_NAMES,
        "source_id": "osgb4000000074565735",
        "name": "Edinburgh",
        "settlement_type": Settlement.Types.CITY,
        "country": Settlement.Countries.SCOTLAND,
        "location": Point(-3.1883, 55.9533, srid=4326),
        "region": region,
    }
    Settlement.objects.create(**values)

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Settlement.objects.create(**values)


@pytest.mark.django_db
def test_deleting_region_preserves_settlement(region):
    settlement = Settlement.objects.create(
        source=Settlement.Sources.OS_OPEN_NAMES,
        source_id="osgb4000000074565735",
        name="Edinburgh",
        settlement_type=Settlement.Types.CITY,
        country=Settlement.Countries.SCOTLAND,
        location=Point(-3.1883, 55.9533, srid=4326),
        region=region,
    )

    region.delete()
    settlement.refresh_from_db()

    assert settlement.region is None


@pytest.mark.django_db
def test_saved_location_string(django_user_model, region):
    user = django_user_model.objects.create_user(
        username="test-user",
        password="test-password",
    )

    saved_location = SavedLocation.objects.create(
        user=user,
        name="Edinburgh",
        location=Point(-3.1883, 55.9533, srid=4326),
        region=region,
    )

    assert str(saved_location) == "Edinburgh"


@pytest.mark.django_db
def test_saved_location_name_is_unique_per_user(django_user_model, region):
    user = django_user_model.objects.create_user(username="test-user")
    location = Point(-3.1883, 55.9533, srid=4326)
    SavedLocation.objects.create(
        user=user,
        name="Home",
        location=location,
        region=region,
    )

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            SavedLocation.objects.create(
                user=user,
                name="Home",
                location=location,
                region=region,
            )


@pytest.mark.django_db
def test_different_users_can_use_same_saved_location_name(
    django_user_model,
    region,
):
    first_user = django_user_model.objects.create_user(username="first-user")
    second_user = django_user_model.objects.create_user(username="second-user")
    location = Point(-3.1883, 55.9533, srid=4326)

    SavedLocation.objects.create(
        user=first_user,
        name="Home",
        location=location,
        region=region,
    )
    SavedLocation.objects.create(
        user=second_user,
        name="Home",
        location=location,
        region=region,
    )

    assert SavedLocation.objects.filter(name="Home").count() == 2


@pytest.mark.django_db
def test_deleting_region_preserves_saved_location(django_user_model, region):
    user = django_user_model.objects.create_user(username="test-user")
    saved_location = SavedLocation.objects.create(
        user=user,
        name="Edinburgh",
        location=Point(-3.1883, 55.9533, srid=4326),
        region=region,
    )

    region.delete()
    saved_location.refresh_from_db()

    assert saved_location.region is None
