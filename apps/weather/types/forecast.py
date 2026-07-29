from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class CurrentConditions:
    observed_at: datetime
    temperature_c: float
    description: str
    wind_speed_mph: float
