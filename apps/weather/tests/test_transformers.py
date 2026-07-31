from datetime import UTC, date, datetime

import pytest

from apps.weather.services.client import (
    CURRENT_VARIABLES,
    DAILY_VARIABLES,
    HOURLY_VARIABLES,
)
from apps.weather.services.exceptions import WeatherServiceError
from apps.weather.services.transformers import (
    normalize_current_conditions,
    normalize_daily_forecast,
    normalize_hourly_forecast,
    weather_code_description,
    weather_code_icon,
)
from apps.weather.types.forecast import (
    CurrentConditions,
    DailyForecastPeriod,
    HourlyForecastPeriod,
)


class FakeVariable:
    def __init__(self, value: float) -> None:
        self.value = value

    def Value(self) -> float:
        return self.value


class FakeCurrentWeather:
    def __init__(
        self,
        observed_at: datetime,
        values: list[float],
    ) -> None:
        self.observed_at = observed_at
        self.values = values

    def Time(self) -> int:
        return int(self.observed_at.timestamp())

    def Variables(self, index: int) -> FakeVariable | None:
        try:
            return FakeVariable(self.values[index])
        except IndexError:
            return None


class FakeHourlyVariable:
    def __init__(self, values: list[float]) -> None:
        self.values = values

    def ValuesAsNumpy(self) -> list[float]:
        return self.values


class FakeHourlyWeather:
    def __init__(
        self,
        starts_at: datetime,
        values: list[list[float]],
        interval: int = 3600,
    ) -> None:
        self.starts_at = starts_at
        self.values = values
        self.interval = interval

    def Time(self) -> int:
        return int(self.starts_at.timestamp())

    def Interval(self) -> int:
        return self.interval

    def Variables(self, index: int) -> FakeHourlyVariable | None:
        try:
            return FakeHourlyVariable(self.values[index])
        except IndexError:
            return None


class FakeDailyVariable:
    def __init__(self, values: list[float]) -> None:
        self.values = values

    def ValuesAsNumpy(self) -> list[float]:
        return self.values

    def ValuesInt64AsNumpy(self) -> list[float]:
        return self.values


class FakeDailyWeather:
    def __init__(
        self,
        starts_at: datetime,
        values: list[list[float]],
        interval: int = 86400,
    ) -> None:
        self.starts_at = starts_at
        self.values = values
        self.interval = interval

    def Time(self) -> int:
        return int(self.starts_at.timestamp())

    def Interval(self) -> int:
        return self.interval

    def Variables(self, index: int) -> FakeDailyVariable | None:
        try:
            return FakeDailyVariable(self.values[index])
        except IndexError:
            return None


class FakeForecastResponse:
    def __init__(
        self,
        current: FakeCurrentWeather | None,
        hourly: FakeHourlyWeather | None = None,
        daily: FakeDailyWeather | None = None,
    ) -> None:
        self.current = current
        self.hourly = hourly
        self.daily = daily

    def Current(self) -> FakeCurrentWeather | None:
        return self.current

    def Hourly(self) -> FakeHourlyWeather | None:
        return self.hourly

    def Daily(self) -> FakeDailyWeather | None:
        return self.daily


def test_normalize_current_conditions_returns_application_type():
    observed_at = datetime(2026, 7, 31, 12, 0, tzinfo=UTC)
    response = FakeForecastResponse(
        FakeCurrentWeather(
            observed_at,
            [
                16.5,
                15.8,
                72.0,
                0.2,
                61.0,
                88.0,
                12.4,
                245.0,
                21.8,
                1.0,
            ],
        )
    )

    conditions = normalize_current_conditions(response)

    assert conditions == CurrentConditions(
        observed_at=observed_at,
        temperature_c=16.5,
        apparent_temperature_c=15.8,
        relative_humidity_percent=72.0,
        precipitation_mm=0.2,
        weather_code=61,
        description="Slight rain",
        icon_name="rain",
        cloud_cover_percent=88.0,
        wind_speed_mph=12.4,
        wind_direction_degrees=245.0,
        wind_gusts_mph=21.8,
        is_day=True,
    )


@pytest.mark.parametrize(
    ("code", "description"),
    [
        (0, "Clear sky"),
        (45, "Fog"),
        (75, "Heavy snowfall"),
        (95, "Thunderstorm"),
        (123, "Unknown conditions"),
    ],
)
def test_weather_code_description(code, description):
    assert weather_code_description(code) == description


@pytest.mark.parametrize(
    ("code", "is_day", "icon_name"),
    [
        (0, True, "clear-day"),
        (0, False, "clear-night"),
        (1, True, "partly-cloudy-day"),
        (2, False, "partly-cloudy-night"),
        (3, False, "cloudy"),
        (45, True, "fog"),
        (51, True, "drizzle"),
        (61, True, "rain"),
        (71, True, "snow"),
        (80, True, "showers-day"),
        (82, False, "showers-night"),
        (95, True, "thunderstorm"),
        (123, True, "unknown"),
    ],
)
def test_weather_code_icon(code, is_day, icon_name):
    assert weather_code_icon(code, is_day=is_day) == icon_name


def test_normalize_current_conditions_rejects_missing_current_data():
    response = FakeForecastResponse(None)

    with pytest.raises(
        WeatherServiceError,
        match="no current conditions",
    ):
        normalize_current_conditions(response)


def test_normalize_current_conditions_rejects_missing_variable():
    observed_at = datetime(2026, 7, 31, 12, 0, tzinfo=UTC)
    values = [0.0] * (len(CURRENT_VARIABLES) - 1)
    response = FakeForecastResponse(
        FakeCurrentWeather(observed_at, values)
    )

    with pytest.raises(
        WeatherServiceError,
        match="omitted current variable: is_day",
    ):
        normalize_current_conditions(response)


def test_normalize_current_conditions_rejects_non_finite_value():
    observed_at = datetime(2026, 7, 31, 12, 0, tzinfo=UTC)
    values = [0.0] * len(CURRENT_VARIABLES)
    values[0] = float("nan")
    response = FakeForecastResponse(
        FakeCurrentWeather(observed_at, values)
    )

    with pytest.raises(
        WeatherServiceError,
        match="invalid value for: temperature_2m",
    ):
        normalize_current_conditions(response)


def test_normalize_hourly_forecast_returns_application_periods():
    starts_at = datetime(2026, 7, 31, 14, 0, tzinfo=UTC)
    response = FakeForecastResponse(
        current=None,
        hourly=FakeHourlyWeather(
            starts_at,
            [
                [16.0, 15.0],
                [15.0, 14.0],
                [0.1, 0.3],
                [2.0, 61.0],
                [8.0, 10.0],
                [1.0, 0.0],
            ],
        ),
    )

    forecast = normalize_hourly_forecast(response)

    assert forecast == [
        HourlyForecastPeriod(
            forecast_at=starts_at,
            temperature_c=16.0,
            apparent_temperature_c=15.0,
            precipitation_mm=0.1,
            weather_code=2,
            description="Partly cloudy",
            icon_name="partly-cloudy-day",
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
            icon_name="rain",
            wind_speed_mph=10.0,
            is_day=False,
        ),
    ]


def test_normalize_hourly_forecast_respects_limit():
    starts_at = datetime(2026, 7, 31, 14, 0, tzinfo=UTC)
    values = [[0.0, 1.0] for _ in HOURLY_VARIABLES]
    response = FakeForecastResponse(
        current=None,
        hourly=FakeHourlyWeather(starts_at, values),
    )

    forecast = normalize_hourly_forecast(response, limit=1)

    assert len(forecast) == 1


def test_normalize_hourly_forecast_rejects_missing_hourly_data():
    response = FakeForecastResponse(current=None, hourly=None)

    with pytest.raises(
        WeatherServiceError,
        match="no hourly forecast",
    ):
        normalize_hourly_forecast(response)


def test_normalize_hourly_forecast_rejects_missing_variable():
    starts_at = datetime(2026, 7, 31, 14, 0, tzinfo=UTC)
    values = [[0.0] for _ in range(len(HOURLY_VARIABLES) - 1)]
    response = FakeForecastResponse(
        current=None,
        hourly=FakeHourlyWeather(starts_at, values),
    )

    with pytest.raises(
        WeatherServiceError,
        match="omitted hourly variable: is_day",
    ):
        normalize_hourly_forecast(response)


def test_normalize_hourly_forecast_rejects_inconsistent_periods():
    starts_at = datetime(2026, 7, 31, 14, 0, tzinfo=UTC)
    values = [[0.0, 1.0] for _ in HOURLY_VARIABLES]
    values[0] = [0.0]
    response = FakeForecastResponse(
        current=None,
        hourly=FakeHourlyWeather(starts_at, values),
    )

    with pytest.raises(
        WeatherServiceError,
        match="inconsistent hourly data",
    ):
        normalize_hourly_forecast(response)


def test_normalize_daily_forecast_returns_application_periods():
    starts_at = datetime(2026, 7, 30, 23, 0, tzinfo=UTC)
    first_sunrise = datetime(2026, 7, 31, 4, 15, tzinfo=UTC)
    first_sunset = datetime(2026, 7, 31, 20, 22, tzinfo=UTC)
    second_sunrise = datetime(2026, 8, 1, 4, 17, tzinfo=UTC)
    second_sunset = datetime(2026, 8, 1, 20, 20, tzinfo=UTC)
    response = FakeForecastResponse(
        current=None,
        daily=FakeDailyWeather(
            starts_at,
            [
                [2.0, 61.0],
                [17.0, 16.0],
                [9.0, 10.0],
                [0.2, 4.6],
                [14.0, 18.0],
                [28.0, 34.0],
                [first_sunrise.timestamp(), second_sunrise.timestamp()],
                [first_sunset.timestamp(), second_sunset.timestamp()],
                [58000.0, 57800.0],
            ],
        ),
    )

    forecast = normalize_daily_forecast(response)

    assert forecast == [
        DailyForecastPeriod(
            forecast_date=date(2026, 7, 31),
            temperature_max_c=17.0,
            temperature_min_c=9.0,
            precipitation_sum_mm=0.2,
            weather_code=2,
            description="Partly cloudy",
            icon_name="partly-cloudy-day",
            wind_speed_max_mph=14.0,
            wind_gusts_max_mph=28.0,
            sunrise_at=first_sunrise,
            sunset_at=first_sunset,
            daylight_hours=58000.0 / 3600,
        ),
        DailyForecastPeriod(
            forecast_date=date(2026, 8, 1),
            temperature_max_c=16.0,
            temperature_min_c=10.0,
            precipitation_sum_mm=4.6,
            weather_code=61,
            description="Slight rain",
            icon_name="rain",
            wind_speed_max_mph=18.0,
            wind_gusts_max_mph=34.0,
            sunrise_at=second_sunrise,
            sunset_at=second_sunset,
            daylight_hours=57800.0 / 3600,
        ),
    ]


def test_normalize_daily_forecast_respects_limit():
    starts_at = datetime(2026, 7, 30, 23, 0, tzinfo=UTC)
    values = [[1.0, 2.0] for _ in DAILY_VARIABLES]
    response = FakeForecastResponse(
        current=None,
        daily=FakeDailyWeather(starts_at, values),
    )

    forecast = normalize_daily_forecast(response, limit=1)

    assert len(forecast) == 1


def test_normalize_daily_forecast_rejects_missing_daily_data():
    response = FakeForecastResponse(current=None, daily=None)

    with pytest.raises(
        WeatherServiceError,
        match="no daily forecast",
    ):
        normalize_daily_forecast(response)


def test_normalize_daily_forecast_rejects_missing_variable():
    starts_at = datetime(2026, 7, 30, 23, 0, tzinfo=UTC)
    values = [[1.0] for _ in range(len(DAILY_VARIABLES) - 1)]
    response = FakeForecastResponse(
        current=None,
        daily=FakeDailyWeather(starts_at, values),
    )

    with pytest.raises(
        WeatherServiceError,
        match="omitted daily variable: daylight_duration",
    ):
        normalize_daily_forecast(response)


def test_normalize_daily_forecast_rejects_inconsistent_periods():
    starts_at = datetime(2026, 7, 30, 23, 0, tzinfo=UTC)
    values = [[1.0, 2.0] for _ in DAILY_VARIABLES]
    values[0] = [1.0]
    response = FakeForecastResponse(
        current=None,
        daily=FakeDailyWeather(starts_at, values),
    )

    with pytest.raises(
        WeatherServiceError,
        match="inconsistent daily data",
    ):
        normalize_daily_forecast(response)
