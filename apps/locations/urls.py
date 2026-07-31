from django.urls import path

from . import views

app_name = "locations"

urlpatterns = [
    path(
        "search/",
        views.region_search,
        name="region_search",
    ),
    path(
        "regions.geojson",
        views.regions_geojson,
        name="regions_geojson",
    ),
    path(
        "regions/<str:code>/panel/",
        views.region_panel,
        name="region_panel",
    ),
]
