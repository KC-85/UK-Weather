from django.shortcuts import render


def detail(request, location):
    return render(request, "weather/detail.html", {"location": location})
