from django.urls import path

from . import views

app_name = "weather"

urlpatterns = [
    path("<slug:location>/", views.detail, name="detail"),
]
