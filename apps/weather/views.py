import logging

from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET

from apps.locations.models import Region

from .services.client import OpenMeteoClient, WeatherClient
from .services.exceptions import WeatherServiceError
from .services.transformers import (
    normalize_current_conditions,
    normalize_hourly_forecast,
)

logger = logging.getLogger(__name__)


@require_GET
def current_conditions(request, code):
    region = get_object_or_404(Region, code=code)
    weather_client = WeatherClient(OpenMeteoClient())

    try:
        response = weather_client.forecast(
            latitude=region.forecast_point.y,
            longitude=region.forecast_point.x,
        )
        conditions = normalize_current_conditions(response)
        hourly_forecast = normalize_hourly_forecast(response)
    except WeatherServiceError as error:
        logger.warning(
            "Unable to load weather for region %s: %s",
            region.code,
            error,
        )
        return render(
            request,
            "weather/partials/weather_error.html",
            {"region": region},
        )

    return render(
        request,
        "weather/partials/current_conditions.html",
        {
            "conditions": conditions,
            "hourly_forecast": hourly_forecast,
            "region": region,
        },
    )


def detail(request, location):
    return render(request, "weather/detail.html", {"location": location})
