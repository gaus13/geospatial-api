# What this file does:
# This will coordinate storage, parsing, measurement, database writes, status
# updates, and processing error handling.
#
# Why it is needed:
# The upload workflow needs one application service so route handlers stay thin
# and PROCESSING, COMPLETED, and FAILED states remain consistent.

"""Application service for upload processing and database persistence."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

import geopandas as gpd
from fastapi import UploadFile
from geoalchemy2.shape import from_shape
from shapely import force_2d
from sqlalchemy.orm import Session

from app.constants import STATUS_COMPLETED, STATUS_FAILED, STATUS_PROCESSING
from app.exceptions import FileProcessingError
from app.models import FeatureRecord, FileRecord
from app.services.measurement import MeasurementResult, compute_measurements
from app.services.parser import parse_geospatial_file
from app.services.storage import save_upload

logger = logging.getLogger(__name__)


def _create_file_record(
    database: Session,
    file_id: UUID,
    filename: str,
) -> FileRecord:
    """Create and persist the initial PROCESSING record."""

    extension = Path(filename).suffix.lower()

    record = FileRecord(
        id=str(file_id),
        filename=filename,
        stored_path=str(Path("uploads") / str(file_id) / f"original{extension}"),
        status=STATUS_PROCESSING,
        feature_count=0,
        created_at=datetime.now(timezone.utc),
    )

    database.add(record)
    database.commit()
    database.refresh(record)

    return record


def _mark_failed(
    database: Session,
    record: FileRecord,
    message: str,
) -> None:
    """Persist a FAILED status and its processing error."""

    database.rollback()

    record.status = STATUS_FAILED
    record.error_message = message
    database.add(record)
    database.commit()
    database.refresh(record)


def _create_feature_records(
    record: FileRecord,
    measurement_result: MeasurementResult,
    geographic_data: gpd.GeoDataFrame,
) -> list[FeatureRecord]:
    """Convert measurement results into database feature records."""

    geographic_2d = geographic_data.to_crs("EPSG:4326")

    feature_records: list[FeatureRecord] = []

    for result, geographic_row in zip(
        measurement_result.features,
        geographic_2d.itertuples(index=False),
    ):
        normalized_geometry = geographic_row.geometry

        postgis_geometry = None

        if normalized_geometry is not None and not normalized_geometry.is_empty:
            postgis_geometry = from_shape(
                force_2d(normalized_geometry),
                srid=4326,
            )

        feature_records.append(
            FeatureRecord(
                file_id=record.id,
                feature_index=result.index,
                geometry_type=result.geometry_type,
                geometry=result.geometry,
                geom=postgis_geometry,
                crs=result.crs,
                properties=result.properties,
                supported=result.supported,
                area=result.area,
                length=result.length,
                unit=result.unit,
                message=result.message,
            )
        )

    return feature_records


async def process_upload(
    upload: UploadFile,
    database: Session,
) -> FileRecord:
    """Process one upload and persist its file and feature measurements."""

    filename = upload.filename or ""
    file_id = uuid4()
    record = _create_file_record(database, file_id, filename)

    try:
        stored_path = await save_upload(upload, file_id)

        extraction_directory = stored_path.parent / "extracted"

        geodataframe = parse_geospatial_file(
            stored_path,
            extraction_directory,
        )

        measurement_result = compute_measurements(geodataframe)

        feature_records = _create_feature_records(
            record,
            measurement_result,
            geodataframe,
        )

        record.stored_path = str(stored_path)
        record.status = STATUS_COMPLETED
        record.feature_count = len(feature_records)
        record.crs = measurement_result.crs
        record.measurement_crs = measurement_result.measurement_crs
        record.error_message = None

        database.add_all(feature_records)
        database.add(record)
        database.commit()
        database.refresh(record)

        return record

    except FileProcessingError as error:
        logger.warning(
            "File processing failed for %s: %s",
            record.id,
            error.message,
        )
        _mark_failed(database, record, error.message)
        error.file_id = record.id
        raise

    except Exception:
        logger.exception("Unexpected file processing failure for %s", record.id)
        _mark_failed(
            database,
            record,
            "Unexpected error while processing file.",
        )
        raise FileProcessingError(
            "Unexpected error while processing file.",
            file_id=record.id,
        )