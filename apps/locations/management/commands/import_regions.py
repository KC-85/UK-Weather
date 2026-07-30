from pathlib import Path

from django.contrib.gis.gdal import DataSource, GDALException
from django.contrib.gis.geos import MultiPolygon
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.locations.models import Region


class Command(BaseCommand):
    help = "Import or update regions from a GDAL-compatible boundary file."

    def add_arguments(self, parser):
        parser.add_argument(
            "source",
            type=Path,
            help="Path to a GeoJSON, GeoPackage, or other GDAL-compatible file.",
        )
        parser.add_argument(
            "--code-field",
            required=True,
            help="Source field containing each region's unique official code.",
        )
        parser.add_argument(
            "--name-field",
            required=True,
            help="Source field containing each region's display name.",
        )
        parser.add_argument(
            "--region-type",
            required=True,
            choices=Region.Types.values,
            help="Region type assigned to every imported feature.",
        )
        parser.add_argument(
            "--layer",
            default="0",
            help="Layer name or zero-based layer index (default: 0).",
        )

    def handle(self, *args, **options):
        source = options["source"]
        if not source.is_file():
            raise CommandError(f"Boundary file does not exist: {source}")

        data_source = self._open_data_source(source)
        layer = self._get_layer(data_source, options["layer"])
        self._validate_fields(
            layer.fields,
            options["code_field"],
            options["name_field"],
        )

        created_count = 0
        updated_count = 0

        with transaction.atomic():
            for feature_number, feature in enumerate(layer, start=1):
                code = self._required_value(
                    feature.get(options["code_field"]),
                    options["code_field"],
                    feature_number,
                )
                name = self._required_value(
                    feature.get(options["name_field"]),
                    options["name_field"],
                    feature_number,
                )
                boundary = self._get_boundary(feature, layer, feature_number)

                _, created = Region.objects.update_or_create(
                    code=code,
                    defaults={
                        "name": name,
                        "region_type": options["region_type"],
                        "boundary": boundary,
                        "forecast_point": boundary.point_on_surface,
                    },
                )
                if created:
                    created_count += 1
                else:
                    updated_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Imported {created_count + updated_count} regions "
                f"({created_count} created, {updated_count} updated)."
            )
        )

    def _open_data_source(self, source):
        try:
            return DataSource(str(source))
        except GDALException as error:
            raise CommandError(f"Could not open boundary file: {error}") from error

    def _get_layer(self, data_source, requested_layer):
        layer_key = (
            int(requested_layer)
            if requested_layer.lstrip("-").isdigit()
            else requested_layer
        )
        try:
            return data_source[layer_key]
        except (GDALException, IndexError, KeyError) as error:
            available = ", ".join(
                f"{index}: {data_source[index].name}"
                for index in range(len(data_source))
            )
            raise CommandError(
                f"Layer {requested_layer!r} was not found. "
                f"Available layers: {available}"
            ) from error

    def _validate_fields(self, available_fields, code_field, name_field):
        missing_fields = [
            field
            for field in (code_field, name_field)
            if field not in available_fields
        ]
        if missing_fields:
            available = ", ".join(available_fields)
            missing = ", ".join(missing_fields)
            raise CommandError(
                f"Missing source field(s): {missing}. "
                f"Available fields: {available}"
            )

    def _required_value(self, value, field_name, feature_number):
        cleaned_value = str(value).strip() if value is not None else ""
        if not cleaned_value:
            raise CommandError(
                f"Feature {feature_number} has no value for {field_name!r}."
            )
        return cleaned_value

    def _get_boundary(self, feature, layer, feature_number):
        try:
            ogr_geometry = feature.geom
            if ogr_geometry.srs is None:
                ogr_geometry.srs = layer.srs
            ogr_geometry.transform(4326)
            boundary = ogr_geometry.geos
        except (GDALException, TypeError, ValueError) as error:
            raise CommandError(
                f"Could not read geometry for feature {feature_number}: {error}"
            ) from error

        if boundary.geom_type == "Polygon":
            boundary = MultiPolygon(boundary, srid=4326)
        elif boundary.geom_type != "MultiPolygon":
            raise CommandError(
                f"Feature {feature_number} has geometry type "
                f"{boundary.geom_type}; expected Polygon or MultiPolygon."
            )

        boundary.srid = 4326
        if boundary.empty:
            raise CommandError(f"Feature {feature_number} has an empty geometry.")
        if not boundary.valid:
            raise CommandError(f"Feature {feature_number} has invalid geometry.")

        return boundary
