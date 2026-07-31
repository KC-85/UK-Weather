from django.contrib import admin
from django.contrib.gis.admin import GISModelAdmin

from .models import Region, SavedLocation, Settlement


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


@admin.register(Settlement)
class SettlementAdmin(GISModelAdmin):
    list_display = (
        "name",
        "settlement_type",
        "country",
        "region",
        "population",
    )
    list_filter = ("settlement_type", "country", "source")
    search_fields = (
        "name",
        "alternate_name",
        "source_id",
        "region__name",
    )
    autocomplete_fields = ("region",)
    list_select_related = ("region",)
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
