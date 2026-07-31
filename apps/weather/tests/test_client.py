from unittest.mock import Mock, sentinel

import pytest
from openmeteo_requests import OpenMeteoRequestsError

from apps.weather.services.client import (
    CURRENT_VARIABLES,
    DAILY_FORECAST_DAYS,
    DAILY_VARIABLES,
    HOURLY_FORECAST_HOURS,
    HOURLY_VARIABLES,
    OPEN_METEO_CACHE_NAME,
    OPEN_METEO_CACHE_SECONDS,
    OPEN_METEO_FORECAST_URL,
    OPEN_METEO_TIMEOUT_SECONDS,
    OpenMeteoClient,
    WeatherClient,
)
from apps.weather.services.exceptions import WeatherServiceError


def test_open_meteo_client_requests_current_hourly_and_daily_forecast():
    api_client = Mock()
    api_client.weather_api.return_value = [sentinel.response]
    client = OpenMeteoClient(api_client=api_client)

    response = client.get_forecast(55.9533, -3.1883)

    assert response is sentinel.response
    api_client.weather_api.assert_called_once_with(
        OPEN_METEO_FORECAST_URL,
        params={
            "latitude": 55.9533,
            "longitude": -3.1883,
            "current": list(CURRENT_VARIABLES),
            "hourly": list(HOURLY_VARIABLES),
            "daily": list(DAILY_VARIABLES),
            "models": "ukmo_seamless",
            "timezone": "Europe/London",
            "forecast_hours": HOURLY_FORECAST_HOURS,
            "forecast_days": DAILY_FORECAST_DAYS,
            "wind_speed_unit": "mph",
        },
        timeout=OPEN_METEO_TIMEOUT_SECONDS,
    )


def test_open_meteo_client_configures_cache_and_retries(monkeypatch):
    cached_session = sentinel.cached_session
    retry_session = sentinel.retry_session
    api_client = sentinel.api_client
    cached_session_factory = Mock(return_value=cached_session)
    retry_factory = Mock(return_value=retry_session)
    client_factory = Mock(return_value=api_client)

    monkeypatch.setattr(
        "apps.weather.services.client.requests_cache.CachedSession",
        cached_session_factory,
    )
    monkeypatch.setattr(
        "apps.weather.services.client.retry",
        retry_factory,
    )
    monkeypatch.setattr(
        "apps.weather.services.client.openmeteo_requests.Client",
        client_factory,
    )

    client = OpenMeteoClient()

    assert client._api_client is api_client
    cached_session_factory.assert_called_once_with(
        OPEN_METEO_CACHE_NAME,
        expire_after=OPEN_METEO_CACHE_SECONDS,
    )
    retry_factory.assert_called_once_with(
        cached_session,
        retries=5,
        backoff_factor=0.2,
    )
    client_factory.assert_called_once_with(session=retry_session)


def test_open_meteo_client_raises_service_error_for_request_failure():
    api_client = Mock()
    api_client.weather_api.side_effect = OpenMeteoRequestsError("offline")
    client = OpenMeteoClient(api_client=api_client)

    with pytest.raises(
        WeatherServiceError,
        match="could not retrieve the forecast",
    ):
        client.get_forecast(55.9533, -3.1883)


def test_open_meteo_client_raises_service_error_for_empty_response():
    api_client = Mock()
    api_client.weather_api.return_value = []
    client = OpenMeteoClient(api_client=api_client)

    with pytest.raises(
        WeatherServiceError,
        match="returned no forecast response",
    ):
        client.get_forecast(55.9533, -3.1883)


def test_weather_client_delegates_to_provider():
    provider = Mock()
    provider.forecast.return_value = sentinel.forecast
    client = WeatherClient(provider)

    response = client.forecast(55.9533, -3.1883)

    assert response is sentinel.forecast
    provider.forecast.assert_called_once_with(55.9533, -3.1883)
