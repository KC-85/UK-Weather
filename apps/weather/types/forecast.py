from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class CurrentConditions:
    observed_at: datetime
    temperature_c: float
    apparent_temperature_c: float
    relative_humidity_percent: float
    precipitation_mm: float
    weather_code: int
    description: str
    cloud_cover_percent: float
    wind_speed_mph: float
    wind_direction_degrees: float
    wind_gusts_mph: float
    is_day: bool


@dataclass(frozen=True, slots=True)
class HourlyForecastPeriod:
    forecast_at: datetime
    temperature_c: float
    apparent_temperature_c: float
    precipitation_mm: float
    weather_code: int
    description: str
    wind_speed_mph: float
    is_day: bool
