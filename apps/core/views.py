from django.conf import settings
from django.shortcuts import render


def home(request):
    return render(request, "core/home.html", {"map_style_url": settings.MAP_STYLE_URL})
