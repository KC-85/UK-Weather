import math
from datetime import UTC, datetime
from typing import Protocol

from apps.weather.types.forecast import CurrentConditions

from .client import CURRENT_VARIABLES
from .exceptions import WeatherServiceError

WMO_WEATHER_DESCRIPTIONS = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    56: "Light freezing drizzle",
    57: "Dense freezing drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Heavy freezing rain",
    71: "Slight snowfall",
    73: "Moderate snowfall",
    75: "Heavy snowfall",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}

CURRENT_VARIABLE_INDEX = {
    name: index for index, name in enumerate(CURRENT_VARIABLES)
}


class CurrentVariable(Protocol):
    def Value(self) -> float: ...


class CurrentWeather(Protocol):
    def Time(self) -> int: ...

    def Variables(self, index: int) -> CurrentVariable | None: ...


class ForecastResponse(Protocol):
    def Current(self) -> CurrentWeather | None: ...


def weather_code_description(code: int) -> str:
    return WMO_WEATHER_DESCRIPTIONS.get(code, "Unknown conditions")


def normalize_current_conditions(
    response: ForecastResponse,
) -> CurrentConditions:
    """Convert an Open-Meteo SDK response into application data."""
    current = response.Current()
    if current is None:
        raise WeatherServiceError(
            "Open-Meteo returned no current conditions."
        )

    weather_code = int(_current_value(current, "weather_code"))

    return CurrentConditions(
        observed_at=datetime.fromtimestamp(current.Time(), tz=UTC),
        temperature_c=_current_value(current, "temperature_2m"),
        apparent_temperature_c=_current_value(
            current,
            "apparent_temperature",
        ),
        relative_humidity_percent=_current_value(
            current,
            "relative_humidity_2m",
        ),
        precipitation_mm=_current_value(current, "precipitation"),
        weather_code=weather_code,
        description=weather_code_description(weather_code),
        cloud_cover_percent=_current_value(current, "cloud_cover"),
        wind_speed_mph=_current_value(current, "wind_speed_10m"),
        wind_direction_degrees=_current_value(
            current,
            "wind_direction_10m",
        ),
        wind_gusts_mph=_current_value(current, "wind_gusts_10m"),
        is_day=bool(_current_value(current, "is_day")),
    )


def _current_value(current: CurrentWeather, variable_name: str) -> float:
    index = CURRENT_VARIABLE_INDEX[variable_name]
    variable = current.Variables(index)

    if variable is None:
        raise WeatherServiceError(
            f"Open-Meteo omitted current variable: {variable_name}."
        )

    value = float(variable.Value())
    if not math.isfinite(value):
        raise WeatherServiceError(
            f"Open-Meteo returned an invalid value for: {variable_name}."
        )

    return value
