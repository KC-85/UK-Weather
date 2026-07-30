from django.core.serializers import serialize
from django.http import HttpResponse

from .models import Region


def regions_geojson(request):
    regions = Region.objects.all()

    geojson = serialize(
        "geojson",
        regions,
        geometry_field="boundary",
        fields=("code", "name", "region_type"),
    )

    return HttpResponse(
        geojson,
        content_type="application/geo+json",
    )
