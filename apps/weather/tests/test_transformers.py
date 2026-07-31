from datetime import UTC, datetime

import pytest

from apps.weather.services.client import CURRENT_VARIABLES
from apps.weather.services.exceptions import WeatherServiceError
from apps.weather.services.transformers import (
    normalize_current_conditions,
    weather_code_description,
)
from apps.weather.types.forecast import CurrentConditions


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


class FakeForecastResponse:
    def __init__(self, current: FakeCurrentWeather | None) -> None:
        self.current = current

    def Current(self) -> FakeCurrentWeather | None:
        return self.current


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
