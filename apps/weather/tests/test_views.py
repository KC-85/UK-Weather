from datetime import UTC, datetime
from unittest.mock import Mock, sentinel

import pytest
from django.contrib.gis.geos import MultiPolygon, Point, Polygon
from django.urls import reverse

from apps.locations.models import Region
from apps.weather.services.exceptions import WeatherServiceError
from apps.weather.types.forecast import (
    CurrentConditions,
    HourlyForecastPeriod,
)


@pytest.fixture
def region(db):
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


@pytest.fixture
def conditions():
    return CurrentConditions(
        observed_at=datetime(2026, 7, 31, 12, 0, tzinfo=UTC),
        temperature_c=16.5,
        apparent_temperature_c=15.8,
        relative_humidity_percent=72.0,
        precipitation_mm=0.2,
        weather_code=61,
        description="Slight rain",
        cloud_cover_percent=88.0,
        wind_speed_mph=12.4,
        wind_direction_degrees=245.0,
        wind_gusts_mph=21.8,
        is_day=True,
    )


@pytest.fixture
def hourly_forecast():
    return [
        HourlyForecastPeriod(
            forecast_at=datetime(2026, 7, 31, 14, 0, tzinfo=UTC),
            temperature_c=16.0,
            apparent_temperature_c=15.0,
            precipitation_mm=0.1,
            weather_code=2,
            description="Partly cloudy",
            wind_speed_mph=8.0,
            is_day=True,
        ),
        HourlyForecastPeriod(
            forecast_at=datetime(2026, 7, 31, 15, 0, tzinfo=UTC),
            temperature_c=15.0,
            apparent_temperature_c=14.0,
            precipitation_mm=0.3,
            weather_code=61,
            description="Slight rain",
            wind_speed_mph=10.0,
            is_day=True,
        ),
    ]


def test_weather_detail(client):
    response = client.get(reverse("weather:detail", args=["london"]))

    assert response.status_code == 200


@pytest.mark.django_db
def test_current_conditions_returns_normalized_forecast(
    client,
    region,
    conditions,
    hourly_forecast,
    monkeypatch,
):
    provider = Mock()
    provider.forecast.return_value = sentinel.raw_response
    provider_factory = Mock(return_value=provider)
    current_transformer = Mock(return_value=conditions)
    hourly_transformer = Mock(return_value=hourly_forecast)
    monkeypatch.setattr(
        "apps.weather.views.OpenMeteoClient",
        provider_factory,
    )
    monkeypatch.setattr(
        "apps.weather.views.normalize_current_conditions",
        current_transformer,
    )
    monkeypatch.setattr(
        "apps.weather.views.normalize_hourly_forecast",
        hourly_transformer,
    )

    response = client.get(
        reverse("weather:current_conditions", args=[region.code])
    )

    assert response.status_code == 200
    assert "weather/partials/current_conditions.html" in [
        template.name for template in response.templates
    ]
    assert response.context["conditions"] == conditions
    assert response.context["hourly_forecast"] == hourly_forecast
    assert response.context["region"] == region
    assert b"Slight rain" in response.content
    assert b"12.4 mph" in response.content
    assert b"City of Edinburgh" in response.content
    assert b"Hourly forecast" in response.content
    assert b"0.1 mm" in response.content
    provider.forecast.assert_called_once_with(55.9533, -3.1883)
    current_transformer.assert_called_once_with(sentinel.raw_response)
    hourly_transformer.assert_called_once_with(sentinel.raw_response)


@pytest.mark.django_db
def test_current_conditions_returns_retryable_error(
    client,
    region,
    monkeypatch,
):
    provider = Mock()
    provider.forecast.side_effect = WeatherServiceError("offline")
    monkeypatch.setattr(
        "apps.weather.views.OpenMeteoClient",
        Mock(return_value=provider),
    )

    response = client.get(
        reverse("weather:current_conditions", args=[region.code])
    )

    assert response.status_code == 200
    assert "weather/partials/weather_error.html" in [
        template.name for template in response.templates
    ]
    assert b"We could not load the forecast" in response.content
    assert b"Try again" in response.content
    assert reverse(
        "weather:current_conditions",
        args=[region.code],
    ).encode() in response.content


@pytest.mark.django_db
def test_current_conditions_returns_not_found_for_unknown_region(
    client,
    monkeypatch,
):
    provider_factory = Mock()
    monkeypatch.setattr(
        "apps.weather.views.OpenMeteoClient",
        provider_factory,
    )

    response = client.get(
        reverse("weather:current_conditions", args=["UNKNOWN"])
    )

    assert response.status_code == 404
    provider_factory.assert_not_called()


@pytest.mark.django_db
def test_current_conditions_rejects_post(client, region):
    response = client.post(
        reverse("weather:current_conditions", args=[region.code])
    )

    assert response.status_code == 405
