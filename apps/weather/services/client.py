from typing import Protocol

import openmeteo_requests
import requests_cache
from openmeteo_requests import OpenMeteoRequestsError
from retry_requests import retry

from .exceptions import WeatherServiceError
from .provider import WeatherProvider

OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
OPEN_METEO_CACHE_NAME = ".openmeteo-cache"
OPEN_METEO_CACHE_SECONDS = 60 * 60
OPEN_METEO_TIMEOUT_SECONDS = 10
HOURLY_FORECAST_HOURS = 24
DAILY_FORECAST_DAYS = 7

CURRENT_VARIABLES = (
    "temperature_2m",
    "apparent_temperature",
    "relative_humidity_2m",
    "precipitation",
    "weather_code",
    "cloud_cover",
    "wind_speed_10m",
    "wind_direction_10m",
    "wind_gusts_10m",
    "is_day",
)

HOURLY_VARIABLES = (
    "temperature_2m",
    "apparent_temperature",
    "precipitation",
    "weather_code",
    "wind_speed_10m",
    "is_day",
)

DAILY_VARIABLES = (
    "weather_code",
    "temperature_2m_max",
    "temperature_2m_min",
    "precipitation_sum",
    "wind_speed_10m_max",
    "wind_gusts_10m_max",
    "sunrise",
    "sunset",
    "daylight_duration",
)


class OpenMeteoApiClient(Protocol):
    def weather_api(
        self,
        url: str,
        params: dict[str, object],
        *,
        timeout: int,
    ) -> list[object]: ...


class OpenMeteoClient:
    """Retrieve UKMO forecast data from Open-Meteo."""

    def __init__(
        self,
        api_client: OpenMeteoApiClient | None = None,
    ) -> None:
        self._api_client = api_client or self._build_api_client()

    @staticmethod
    def _build_api_client() -> OpenMeteoApiClient:
        cache_session = requests_cache.CachedSession(
            OPEN_METEO_CACHE_NAME,
            expire_after=OPEN_METEO_CACHE_SECONDS,
        )
        retry_session = retry(
            cache_session,
            retries=5,
            backoff_factor=0.2,
        )
        return openmeteo_requests.Client(session=retry_session)

    def get_forecast(self, latitude: float, longitude: float) -> object:
        params: dict[str, object] = {
            "latitude": latitude,
            "longitude": longitude,
            "current": list(CURRENT_VARIABLES),
            "hourly": list(HOURLY_VARIABLES),
            "daily": list(DAILY_VARIABLES),
            "models": "ukmo_seamless",
            "timezone": "Europe/London",
            "forecast_hours": HOURLY_FORECAST_HOURS,
            "forecast_days": DAILY_FORECAST_DAYS,
            "wind_speed_unit": "mph",
        }

        try:
            responses = self._api_client.weather_api(
                OPEN_METEO_FORECAST_URL,
                params=params,
                timeout=OPEN_METEO_TIMEOUT_SECONDS,
            )
        except OpenMeteoRequestsError as error:
            raise WeatherServiceError(
                "Open-Meteo could not retrieve the forecast."
            ) from error

        if not responses:
            raise WeatherServiceError(
                "Open-Meteo returned no forecast response."
            )

        return responses[0]

    def forecast(self, latitude: float, longitude: float) -> object:
        """Satisfy the generic WeatherProvider interface."""
        return self.get_forecast(latitude, longitude)


class WeatherClient:
    def __init__(self, provider: WeatherProvider) -> None:
        self.provider = provider

    def forecast(self, latitude: float, longitude: float):
        return self.provider.forecast(latitude, longitude)
