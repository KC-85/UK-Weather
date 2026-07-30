from django.urls import path

from . import views

app_name = "locations"

urlpatterns = [
    path("search/", views.search, name="search"),
    path(
        "regions.geojson",
        views.regions_geojson,
        name="regions_geojson",
    ),
]
