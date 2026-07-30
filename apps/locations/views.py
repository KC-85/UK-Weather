import json
import math

from django.contrib.gis.db.models.functions import AsGeoJSON, GeomOutputGeoFunc
from django.contrib.gis.geos import Polygon
from django.http import JsonResponse

from .models import Region

DEFAULT_SIMPLIFICATION_TOLERANCE = 0.001
MAX_SIMPLIFICATION_TOLERANCE = 0.1


class SimplifyPreserveTopology(GeomOutputGeoFunc):
    function = "ST_SimplifyPreserveTopology"
    arity = 2


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
