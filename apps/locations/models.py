from django.conf import settings
from django.contrib.gis.db import models


class Region(models.Model):
    class Types(models.TextChoices):
        NATION = 'nation', 'Nation'
        REGION = 'region', 'Region'
        LOCAL_AUTHORITY = 'local_authority', 'Local Authority'

    code = models.CharField(max_length=16, unique=True)
    name = models.CharField(max_length=150)
    region_type = models.CharField(max_length=32, choices=Types.choices)

    parent = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='children',
    )

    boundary = models.MultiPolygonField(srid=4326)
    forecast_point = models.PointField(srid=4326)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class SavedLocation(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='saved_locations',
    )
    name = models.CharField(max_length=150)

    location = models.PointField(srid=4326)

    region = models.ForeignKey(
        Region,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='saved_locations',
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'name'],
                name='unique_saved_location_name_per_user',
            ),
        ]

    def __str__(self):
        return self.name
