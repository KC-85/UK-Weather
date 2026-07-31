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


class Settlement(models.Model):
    class Types(models.TextChoices):
        CITY = 'city', 'City'
        TOWN = 'town', 'Town'
        VILLAGE = 'village', 'Village'
        HAMLET = 'hamlet', 'Hamlet'

    class Sources(models.TextChoices):
        OS_OPEN_NAMES = 'os_open_names', 'OS Open Names'

    class Countries(models.TextChoices):
        ENGLAND = 'England', 'England'
        SCOTLAND = 'Scotland', 'Scotland'
        WALES = 'Wales', 'Wales'
        NORTHERN_IRELAND = 'Northern Ireland', 'Northern Ireland'

    source = models.CharField(max_length=32, choices=Sources.choices)
    source_id = models.CharField(max_length=100)
    name = models.CharField(max_length=150)
    alternate_name = models.CharField(max_length=150, blank=True)
    settlement_type = models.CharField(max_length=16, choices=Types.choices)
    country = models.CharField(max_length=32, choices=Countries.choices)
    location = models.PointField(srid=4326)
    population = models.PositiveIntegerField(null=True, blank=True)
    region = models.ForeignKey(
        Region,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='settlements',
    )

    class Meta:
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(
                fields=['source', 'source_id'],
                name='unique_settlement_source_id',
            ),
        ]
        indexes = [
            models.Index(
                fields=['settlement_type', 'name'],
                name='settlement_type_name_idx',
            ),
        ]

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
