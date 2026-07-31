from django.urls import path

from . import views

app_name = "weather"

urlpatterns = [
    path(
        "regions/<str:code>/current/",
        views.current_conditions,
        name="current_conditions",
    ),
    path("<slug:location>/", views.detail, name="detail"),
]
