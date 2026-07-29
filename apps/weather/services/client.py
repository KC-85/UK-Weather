from .provider import WeatherProvider


class WeatherClient:
    def __init__(self, provider: WeatherProvider) -> None:
        self.provider = provider

    def forecast(self, latitude: float, longitude: float):
        return self.provider.forecast(latitude, longitude)
