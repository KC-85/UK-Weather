from django.shortcuts import render

from .forms import LocationSearchForm


def search(request):
    form = LocationSearchForm(request.GET)
    context = {"form": form, "query": ""}

    if form.is_valid():
        context["query"] = form.cleaned_data["query"]

    return render(request, "locations/partials/search_results.html", context)
