import pytest

from apps.locations.models import SavedLocation


@pytest.mark.django_db
def test_saved_location_string(django_user_model):
    user = django_user_model(username="test-user")
    location = SavedLocation(
        user=user,
        name="Edinburgh",
        latitude="55.953300",
        longitude="-3.188300",
    )

    assert str(location) == "Edinburgh"
