import json
import math

from django.contrib.gis.db.models.functions import (
    AsGeoJSON,
    Envelope,
    GeomOutputGeoFunc,
)
from django.contrib.gis.geos import Polygon
from django.db.models import Case, IntegerField, Value, When
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET

from .forms import LocationSearchForm
from .models import Region

DEFAULT_SIMPLIFICATION_TOLERANCE = 0.001
MAX_SIMPLIFICATION_TOLERANCE = 0.1
REGION_SEARCH_LIMIT = 8


class SimplifyPreserveTopology(GeomOutputGeoFunc):
    function = "ST_SimplifyPreserveTopology"
    arity = 2


@require_GET
def region_search(request):
    raw_query = request.GET.get("query", "")
    query = raw_query.strip()
    regions = Region.objects.none()

    if query:
        form = LocationSearchForm({"query": raw_query})
        if form.is_valid():
            query = form.cleaned_data["query"]
            regions = (
                Region.objects.filter(name__icontains=query)
                .annotate(
                    search_rank=Case(
                        When(name__iexact=query, then=Value(0)),
                        When(name__istartswith=query, then=Value(1)),
                        default=Value(2),
                        output_field=IntegerField(),
                    ),
                    search_envelope=Envelope("boundary"),
                )
                .only("code", "name", "region_type")
                .order_by("search_rank", "name")[:REGION_SEARCH_LIMIT]
            )
    else:
        form = LocationSearchForm()

    return render(
        request,
        "locations/partials/search_results.html",
        {
            "form": form,
            "query": query,
            "regions": regions,
        },
    )


def region_panel(request, code):
    region = get_object_or_404(Region, code=code)
    return render(
        request,
        "locations/partials/region_panel.html",
        {"region": region},
    )


def regions_geojson(request):
    try:
        bounds = _parse_bbox(request.GET.get("bbox"))
        tolerance = _parse_tolerance(request.GET.get("tolerance"))
    except ValueError as error:
        return JsonResponse({"error": str(error)}, status=400)

    regions = Region.objects.all()
    if bounds is not None:
        regions = regions.filter(boundary__intersects=bounds)

    regions = regions.annotate(
        map_geometry=AsGeoJSON(
            SimplifyPreserveTopology("boundary", tolerance),
            precision=6,
        )
    ).values("id", "code", "name", "region_type", "map_geometry")

    features = [
        {
            "type": "Feature",
            "id": region["id"],
            "properties": {
                "code": region["code"],
                "name": region["name"],
                "region_type": region["region_type"],
            },
            "geometry": json.loads(region["map_geometry"]),
        }
        for region in regions
    ]

    return JsonResponse(
        {
            "type": "FeatureCollection",
            "features": features,
        },
        content_type="application/geo+json",
    )


def _parse_bbox(raw_bbox):
    if raw_bbox is None:
        return None

    try:
        coordinates = [float(value) for value in raw_bbox.split(",")]
    except ValueError as error:
        raise ValueError(
            "bbox must contain four comma-separated numbers."
        ) from error

    if len(coordinates) != 4 or not all(map(math.isfinite, coordinates)):
        raise ValueError("bbox must contain four comma-separated numbers.")

    west, south, east, north = coordinates
    if not (-180 <= west < east <= 180):
        raise ValueError("bbox west/east values are invalid.")
    if not (-90 <= south < north <= 90):
        raise ValueError("bbox south/north values are invalid.")

    bounds = Polygon.from_bbox(coordinates)
    bounds.srid = 4326
    return bounds


def _parse_tolerance(raw_tolerance):
    if raw_tolerance is None:
        return DEFAULT_SIMPLIFICATION_TOLERANCE

    try:
        tolerance = float(raw_tolerance)
    except ValueError as error:
        raise ValueError("tolerance must be a number.") from error

    if (
        not math.isfinite(tolerance)
        or tolerance < 0
        or tolerance > MAX_SIMPLIFICATION_TOLERANCE
    ):
        raise ValueError(
            f"tolerance must be between 0 and "
            f"{MAX_SIMPLIFICATION_TOLERANCE}."
        )

    return tolerance
