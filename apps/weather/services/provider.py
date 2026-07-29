from typing import Protocol


class WeatherProvider(Protocol):
    def forecast(self, latitude: float, longitude: float):
        """Return normalized forecast data for a coordinate."""
        ...
