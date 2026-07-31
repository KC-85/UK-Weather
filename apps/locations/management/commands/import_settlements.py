import sqlite3
from pathlib import Path

from django.contrib.gis.gdal import GDALException
from django.contrib.gis.geos import GEOSException, GEOSGeometry
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import OuterRef, Subquery

from apps.locations.models import Region, Settlement

SOURCE_SRID = 27700
TARGET_SRID = 4326
SOURCE_TABLE = "named_place"
SOURCE_TYPE = "populatedPlace"
DEFAULT_BATCH_SIZE = 500
GEOPACKAGE_MAGIC = b"GP"
GEOPACKAGE_BASE_HEADER_SIZE = 8
GEOPACKAGE_ENVELOPE_SIZES = {
    0: 0,
    1: 32,
    2: 48,
    3: 48,
    4: 64,
}
SOURCE_TYPE_MAP = {
    label: value for value, label in Settlement.Types.choices
}
REQUIRED_COLUMNS = {
    "id",
    "name1",
    "name1_lang",
    "name2",
    "name2_lang",
    "type",
    "local_type",
    "geometry",
    "country",
}


class Command(BaseCommand):
    help = "Import cities and towns from an OS Open Names GeoPackage."

    def add_arguments(self, parser):
        parser.add_argument(
            "source",
            type=Path,
            help="Path to the OS Open Names GeoPackage.",
        )
        parser.add_argument(
            "--types",
            nargs="+",
            choices=tuple(SOURCE_TYPE_MAP),
            default=["City", "Town"],
            help="Settlement types to import (default: City Town).",
        )
        parser.add_argument(
            "--limit",
            type=int,
            help="Import at most this many matching records.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Validate and transform the source without writing data.",
        )

    def handle(self, *args, **options):
        source = options["source"]
        limit = options["limit"]

        if not source.is_file():
            raise CommandError(f"OS Open Names file does not exist: {source}")
        if limit is not None and limit <= 0:
            raise CommandError("limit must be a positive integer.")

        source_rows = self._read_source(
            source,
            options["types"],
            limit=limit,
        )
        settlements = [
            self._build_settlement(row, row_number)
            for row_number, row in enumerate(source_rows, start=1)
        ]

        if options["dry_run"]:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Validated {len(settlements)} settlements. "
                    "Dry run complete; no data was written."
                )
            )
            return

        source_ids = [settlement.source_id for settlement in settlements]
        existing_ids = set(
            Settlement.objects.filter(
                source=Settlement.Sources.OS_OPEN_NAMES,
                source_id__in=source_ids,
            ).values_list("source_id", flat=True)
        )

        with transaction.atomic():
            Settlement.objects.bulk_create(
                settlements,
                batch_size=DEFAULT_BATCH_SIZE,
                update_conflicts=True,
                update_fields=[
                    "name",
                    "alternate_name",
                    "settlement_type",
                    "country",
                    "location",
                ],
                unique_fields=["source", "source_id"],
            )
            self._assign_regions()

        created_count = len(settlements) - len(existing_ids)
        updated_count = len(existing_ids)
        unmatched_count = Settlement.objects.filter(
            source=Settlement.Sources.OS_OPEN_NAMES,
            source_id__in=source_ids,
            region__isnull=True,
        ).count()

        self.stdout.write(
            self.style.SUCCESS(
                f"Imported {len(settlements)} settlements "
                f"({created_count} created, {updated_count} updated; "
                f"{unmatched_count} without an authority)."
            )
        )

    def _read_source(self, source, requested_types, *, limit):
        uri = f"{source.resolve().as_uri()}?mode=ro"

        try:
            with sqlite3.connect(uri, uri=True) as connection:
                connection.row_factory = sqlite3.Row
                self._validate_schema(connection)

                placeholders = ", ".join("?" for _ in requested_types)
                query = (
                    "SELECT id, name1, name1_lang, name2, name2_lang, "
                    "local_type, geometry, country "
                    f"FROM {SOURCE_TABLE} "
                    "WHERE type = ? "
                    f"AND local_type IN ({placeholders}) "
                    "ORDER BY id"
                )
                parameters = [SOURCE_TYPE, *requested_types]

                if limit is not None:
                    query = f"{query} LIMIT ?"
                    parameters.append(limit)

                return connection.execute(query, parameters).fetchall()
        except sqlite3.DatabaseError as error:
            raise CommandError(
                f"Could not read OS Open Names GeoPackage: {error}"
            ) from error

    def _validate_schema(self, connection):
        table_exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            [SOURCE_TABLE],
        ).fetchone()
        if table_exists is None:
            raise CommandError(
                f"OS Open Names layer {SOURCE_TABLE!r} was not found."
            )

        columns = {
            row[1]
            for row in connection.execute(
                f"PRAGMA table_info({SOURCE_TABLE})"
            ).fetchall()
        }
        missing_columns = sorted(REQUIRED_COLUMNS - columns)
        if missing_columns:
            raise CommandError(
                "OS Open Names layer is missing column(s): "
                f"{', '.join(missing_columns)}."
            )

    def _build_settlement(self, row, row_number):
        source_id = self._required_text(
            row["id"],
            "id",
            row_number,
            max_length=100,
        )
        name, alternate_name = self._display_names(row, row_number)
        source_type = self._required_text(
            row["local_type"],
            "local_type",
            row_number,
            max_length=32,
        )
        country = self._required_text(
            row["country"],
            "country",
            row_number,
            max_length=32,
        )

        if source_type not in SOURCE_TYPE_MAP:
            raise CommandError(
                f"Feature {row_number} has unsupported local_type: "
                f"{source_type}."
            )
        if country not in Settlement.Countries.values:
            raise CommandError(
                f"Feature {row_number} has unsupported country: {country}."
            )

        location = self._location(row, row_number)

        return Settlement(
            source=Settlement.Sources.OS_OPEN_NAMES,
            source_id=source_id,
            name=name,
            alternate_name=alternate_name,
            settlement_type=SOURCE_TYPE_MAP[source_type],
            country=country,
            location=location,
        )

    def _display_names(self, row, row_number):
        name1 = self._required_text(
            row["name1"],
            "name1",
            row_number,
            max_length=150,
        )
        name2 = self._optional_text(
            row["name2"],
            "name2",
            row_number,
            max_length=150,
        )
        name1_language = self._clean_text(row["name1_lang"]).lower()
        name2_language = self._clean_text(row["name2_lang"]).lower()

        if name2 and name2_language == "eng" and name1_language != "eng":
            return name2, name1
        if name2 == name1:
            name2 = ""
        return name1, name2

    def _location(self, row, row_number):
        try:
            geometry_blob = bytes(row["geometry"])
            wkb_offset, source_srid = self._geometry_header(
                geometry_blob,
                row_number,
            )
            location = GEOSGeometry(memoryview(geometry_blob[wkb_offset:]))
            location.srid = source_srid

            if location.geom_type != "Point":
                raise ValueError(
                    f"geometry type is {location.geom_type}; expected Point"
                )
            if location.empty:
                raise ValueError("geometry is empty")

            location.transform(TARGET_SRID)
            return location
        except (
            GDALException,
            GEOSException,
            KeyError,
            TypeError,
            ValueError,
        ) as error:
            raise CommandError(
                f"Could not transform feature {row_number}: {error}"
            ) from error

    def _geometry_header(self, geometry_blob, row_number):
        if (
            len(geometry_blob) < GEOPACKAGE_BASE_HEADER_SIZE
            or geometry_blob[:2] != GEOPACKAGE_MAGIC
        ):
            raise ValueError(
                f"feature {row_number} has an invalid GeoPackage geometry"
            )

        flags = geometry_blob[3]
        envelope_type = (flags >> 1) & 0b111
        envelope_size = GEOPACKAGE_ENVELOPE_SIZES.get(envelope_type)
        if envelope_size is None:
            raise ValueError(
                f"feature {row_number} uses an unsupported geometry envelope"
            )

        byte_order = "little" if flags & 0b1 else "big"
        source_srid = int.from_bytes(
            geometry_blob[4:8],
            byteorder=byte_order,
            signed=True,
        )
        if source_srid != SOURCE_SRID:
            raise ValueError(
                f"feature {row_number} uses SRID {source_srid}; "
                f"expected {SOURCE_SRID}"
            )

        wkb_offset = GEOPACKAGE_BASE_HEADER_SIZE + envelope_size
        if len(geometry_blob) <= wkb_offset:
            raise ValueError(
                f"feature {row_number} has no geometry payload"
            )

        return wkb_offset, source_srid

    def _assign_regions(self):
        containing_authority = (
            Region.objects.filter(
                region_type=Region.Types.LOCAL_AUTHORITY,
                boundary__covers=OuterRef("location"),
            )
            .order_by("pk")
            .values("pk")[:1]
        )
        Settlement.objects.filter(
            source=Settlement.Sources.OS_OPEN_NAMES,
        ).update(region_id=Subquery(containing_authority))

    def _required_text(
        self,
        value,
        field_name,
        row_number,
        *,
        max_length,
    ):
        cleaned_value = self._clean_text(value)
        if not cleaned_value:
            raise CommandError(
                f"Feature {row_number} has no value for {field_name!r}."
            )
        if len(cleaned_value) > max_length:
            raise CommandError(
                f"Feature {row_number} value for {field_name!r} exceeds "
                f"{max_length} characters."
            )
        return cleaned_value

    def _optional_text(
        self,
        value,
        field_name,
        row_number,
        *,
        max_length,
    ):
        cleaned_value = self._clean_text(value)
        if len(cleaned_value) > max_length:
            raise CommandError(
                f"Feature {row_number} value for {field_name!r} exceeds "
                f"{max_length} characters."
            )
        return cleaned_value

    @staticmethod
    def _clean_text(value):
        return str(value).strip() if value is not None else ""
