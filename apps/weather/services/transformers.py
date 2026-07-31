import math
from datetime import UTC, datetime
from typing import Protocol
from zoneinfo import ZoneInfo

from apps.weather.types.forecast import (
    CurrentConditions,
    DailyForecastPeriod,
    HourlyForecastPeriod,
)

from .client import (
    CURRENT_VARIABLES,
    DAILY_FORECAST_DAYS,
    DAILY_VARIABLES,
    HOURLY_FORECAST_HOURS,
    HOURLY_VARIABLES,
)
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
HOURLY_VARIABLE_INDEX = {
    name: index for index, name in enumerate(HOURLY_VARIABLES)
}
DAILY_VARIABLE_INDEX = {
    name: index for index, name in enumerate(DAILY_VARIABLES)
}
DAILY_TIMESTAMP_VARIABLES = {"sunrise", "sunset"}
UK_TIMEZONE = ZoneInfo("Europe/London")


class CurrentVariable(Protocol):
    def Value(self) -> float: ...


class CurrentWeather(Protocol):
    def Time(self) -> int: ...

    def Variables(self, index: int) -> CurrentVariable | None: ...


class HourlyValues(Protocol):
    def __len__(self) -> int: ...

    def __getitem__(self, index: int) -> float: ...


class HourlyVariable(Protocol):
    def ValuesAsNumpy(self) -> HourlyValues: ...


class HourlyWeather(Protocol):
    def Time(self) -> int: ...

    def Interval(self) -> int: ...

    def Variables(self, index: int) -> HourlyVariable | None: ...


class DailyVariable(Protocol):
    def ValuesAsNumpy(self) -> HourlyValues: ...

    def ValuesInt64AsNumpy(self) -> HourlyValues: ...


class DailyWeather(Protocol):
    def Time(self) -> int: ...

    def Interval(self) -> int: ...

    def Variables(self, index: int) -> DailyVariable | None: ...


class ForecastResponse(Protocol):
    def Current(self) -> CurrentWeather | None: ...

    def Hourly(self) -> HourlyWeather | None: ...

    def Daily(self) -> DailyWeather | None: ...


def weather_code_description(code: int) -> str:
    return WMO_WEATHER_DESCRIPTIONS.get(code, "Unknown conditions")


def weather_code_icon(code: int, *, is_day: bool = True) -> str:
    """Map a WMO weather code to a local SVG symbol name."""
    if code == 0:
        return "clear-day" if is_day else "clear-night"
    if code in {1, 2}:
        return "partly-cloudy-day" if is_day else "partly-cloudy-night"
    if code == 3:
        return "cloudy"
    if code in {45, 48}:
        return "fog"
    if code in {51, 53, 55, 56, 57}:
        return "drizzle"
    if code in {61, 63, 65, 66, 67}:
        return "rain"
    if code in {71, 73, 75, 77, 85, 86}:
        return "snow"
    if code in {80, 81, 82}:
        return "showers-day" if is_day else "showers-night"
    if code in {95, 96, 99}:
        return "thunderstorm"
    return "unknown"


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
    is_day = bool(_current_value(current, "is_day"))

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
        icon_name=weather_code_icon(weather_code, is_day=is_day),
        cloud_cover_percent=_current_value(current, "cloud_cover"),
        wind_speed_mph=_current_value(current, "wind_speed_10m"),
        wind_direction_degrees=_current_value(
            current,
            "wind_direction_10m",
        ),
        wind_gusts_mph=_current_value(current, "wind_gusts_10m"),
        is_day=is_day,
    )


def normalize_hourly_forecast(
    response: ForecastResponse,
    limit: int = HOURLY_FORECAST_HOURS,
) -> list[HourlyForecastPeriod]:
    """Convert Open-Meteo hourly arrays into forecast periods."""
    hourly = response.Hourly()
    if hourly is None:
        raise WeatherServiceError("Open-Meteo returned no hourly forecast.")

    if limit <= 0:
        raise ValueError("Hourly forecast limit must be positive.")

    interval = hourly.Interval()
    if interval <= 0:
        raise WeatherServiceError(
            "Open-Meteo returned an invalid hourly interval."
        )

    values_by_name = {
        name: _hourly_values(hourly, name) for name in HOURLY_VARIABLES
    }
    lengths = {len(values) for values in values_by_name.values()}

    if not lengths or lengths == {0}:
        raise WeatherServiceError("Open-Meteo returned no hourly periods.")

    if len(lengths) != 1:
        raise WeatherServiceError(
            "Open-Meteo returned inconsistent hourly data."
        )

    period_count = min(limit, lengths.pop())
    forecast = []

    for index in range(period_count):
        weather_code = int(
            _hourly_value(values_by_name, "weather_code", index)
        )
        is_day = bool(_hourly_value(values_by_name, "is_day", index))
        forecast.append(
            HourlyForecastPeriod(
                forecast_at=datetime.fromtimestamp(
                    hourly.Time() + (index * interval),
                    tz=UTC,
                ),
                temperature_c=_hourly_value(
                    values_by_name,
                    "temperature_2m",
                    index,
                ),
                apparent_temperature_c=_hourly_value(
                    values_by_name,
                    "apparent_temperature",
                    index,
                ),
                precipitation_mm=_hourly_value(
                    values_by_name,
                    "precipitation",
                    index,
                ),
                weather_code=weather_code,
                description=weather_code_description(weather_code),
                icon_name=weather_code_icon(
                    weather_code,
                    is_day=is_day,
                ),
                wind_speed_mph=_hourly_value(
                    values_by_name,
                    "wind_speed_10m",
                    index,
                ),
                is_day=is_day,
            )
        )

    return forecast


def normalize_daily_forecast(
    response: ForecastResponse,
    limit: int = DAILY_FORECAST_DAYS,
) -> list[DailyForecastPeriod]:
    """Convert Open-Meteo daily arrays into forecast periods."""
    daily = response.Daily()
    if daily is None:
        raise WeatherServiceError("Open-Meteo returned no daily forecast.")

    if limit <= 0:
        raise ValueError("Daily forecast limit must be positive.")

    interval = daily.Interval()
    if interval <= 0:
        raise WeatherServiceError(
            "Open-Meteo returned an invalid daily interval."
        )

    values_by_name = {
        name: _daily_values(daily, name) for name in DAILY_VARIABLES
    }
    lengths = {len(values) for values in values_by_name.values()}

    if not lengths or lengths == {0}:
        raise WeatherServiceError("Open-Meteo returned no daily periods.")

    if len(lengths) != 1:
        raise WeatherServiceError(
            "Open-Meteo returned inconsistent daily data."
        )

    period_count = min(limit, lengths.pop())
    forecast = []

    for index in range(period_count):
        weather_code = int(
            _daily_value(values_by_name, "weather_code", index)
        )
        period_start = datetime.fromtimestamp(
            daily.Time() + (index * interval),
            tz=UTC,
        )
        forecast.append(
            DailyForecastPeriod(
                forecast_date=period_start.astimezone(UK_TIMEZONE).date(),
                temperature_max_c=_daily_value(
                    values_by_name,
                    "temperature_2m_max",
                    index,
                ),
                temperature_min_c=_daily_value(
                    values_by_name,
                    "temperature_2m_min",
                    index,
                ),
                precipitation_sum_mm=_daily_value(
                    values_by_name,
                    "precipitation_sum",
                    index,
                ),
                weather_code=weather_code,
                description=weather_code_description(weather_code),
                icon_name=weather_code_icon(weather_code),
                wind_speed_max_mph=_daily_value(
                    values_by_name,
                    "wind_speed_10m_max",
                    index,
                ),
                wind_gusts_max_mph=_daily_value(
                    values_by_name,
                    "wind_gusts_10m_max",
                    index,
                ),
                sunrise_at=_daily_datetime(
                    values_by_name,
                    "sunrise",
                    index,
                ),
                sunset_at=_daily_datetime(
                    values_by_name,
                    "sunset",
                    index,
                ),
                daylight_hours=(
                    _daily_value(
                        values_by_name,
                        "daylight_duration",
                        index,
                    )
                    / 3600
                ),
            )
        )

    return forecast


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


def _hourly_values(
    hourly: HourlyWeather,
    variable_name: str,
) -> HourlyValues:
    index = HOURLY_VARIABLE_INDEX[variable_name]
    variable = hourly.Variables(index)

    if variable is None:
        raise WeatherServiceError(
            f"Open-Meteo omitted hourly variable: {variable_name}."
        )

    return variable.ValuesAsNumpy()


def _hourly_value(
    values_by_name: dict[str, HourlyValues],
    variable_name: str,
    index: int,
) -> float:
    value = float(values_by_name[variable_name][index])

    if not math.isfinite(value):
        raise WeatherServiceError(
            f"Open-Meteo returned an invalid hourly value for: "
            f"{variable_name}."
        )

    return value


def _daily_values(
    daily: DailyWeather,
    variable_name: str,
) -> HourlyValues:
    index = DAILY_VARIABLE_INDEX[variable_name]
    variable = daily.Variables(index)

    if variable is None:
        raise WeatherServiceError(
            f"Open-Meteo omitted daily variable: {variable_name}."
        )

    if variable_name in DAILY_TIMESTAMP_VARIABLES:
        return variable.ValuesInt64AsNumpy()

    return variable.ValuesAsNumpy()


def _daily_value(
    values_by_name: dict[str, HourlyValues],
    variable_name: str,
    index: int,
) -> float:
    value = float(values_by_name[variable_name][index])

    if not math.isfinite(value):
        raise WeatherServiceError(
            f"Open-Meteo returned an invalid daily value for: "
            f"{variable_name}."
        )

    return value


def _daily_datetime(
    values_by_name: dict[str, HourlyValues],
    variable_name: str,
    index: int,
) -> datetime:
    timestamp = _daily_value(values_by_name, variable_name, index)

    if timestamp <= 0:
        raise WeatherServiceError(
            f"Open-Meteo returned an invalid daily value for: "
            f"{variable_name}."
        )

    return datetime.fromtimestamp(timestamp, tz=UTC)
