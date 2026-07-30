from django.contrib import admin
from django.contrib.gis.admin import GISModelAdmin

from .models import Region, SavedLocation


@admin.register(Region)
class RegionAdmin(GISModelAdmin):
    list_display = (
        "name",
        "code",
        "region_type",
        "parent",
    )
    list_filter = ("region_type",)
    search_fields = ("name", "code")
    autocomplete_fields = ("parent",)
    ordering = ("name",)


@admin.register(SavedLocation)
class SavedLocationAdmin(GISModelAdmin):
    list_display = (
        "name",
        "user",
        "region",
        "created_at",
    )
    search_fields = (
        "name",
        "user__username",
        "region__name",
    )
    autocomplete_fields = ("user", "region")
    list_select_related = ("user", "region")
    readonly_fields = ("created_at",)
    ordering = ("name",)
