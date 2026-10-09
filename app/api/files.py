# What this file does:
# This will expose the upload, file-information, and measurements endpoints.
#
# Why it is needed:
# These are the three required API operations, while processing logic belongs
# in services rather than inside route handlers.

"""API routes for uploading files and retrieving measurements."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.exceptions import FileProcessingError, UnsupportedFileError
from app.models import FeatureRecord, FileRecord
from app.schemas import (
    FeatureMeasurementResponse,
    FileResponse,
    MeasurementsResponse,
)
from app.services.file_service import process_upload

router = APIRouter(
    prefix="/api/files",
    tags=["files"],
)


@router.post(
    "/",
    response_model=FileResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_file(
    file: UploadFile | None = File(None),
    database: Session = Depends(get_db),
) -> FileRecord:
    """Upload and synchronously process a KML or Shapefile archive."""

    if file is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Unsupported file type. Upload a .kml or a .zip "
                "containing a Shapefile."
            ),
        )

    try:
        return await process_upload(file, database)

    except UnsupportedFileError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error.message,
        ) from error

    except FileProcessingError as error:
        message = error.message.lower()

        if "too large" in message:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=error.message,
            ) from error

        if "empty" in message:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error.message,
            ) from error

        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "detail": error.message,
                "id": error.file_id,
                "status": "FAILED",
            },
        ) from error


@router.get(
    "/{file_id}/",
    response_model=FileResponse,
)
def get_file(
    file_id: UUID,
    database: Session = Depends(get_db),
) -> FileRecord:
    """Return information about one uploaded file."""

    record = database.scalar(
        select(FileRecord).where(FileRecord.id == str(file_id))
    )

    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found.",
        )

    return record


@router.get(
    "/{file_id}/measurements/",
    response_model=MeasurementsResponse,
)
def get_file_measurements(
    file_id: UUID,
    database: Session = Depends(get_db),
) -> MeasurementsResponse:
    """Return all stored feature measurements for one uploaded file."""

    record = database.scalar(
        select(FileRecord).where(FileRecord.id == str(file_id))
    )

    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found.",
        )

    features = database.scalars(
        select(FeatureRecord)
        .where(FeatureRecord.file_id == str(file_id))
        .order_by(FeatureRecord.feature_index)
    ).all()

    measurements = [
        FeatureMeasurementResponse(
            index=feature.feature_index,
            geometry_type=feature.geometry_type,
            geometry=feature.geometry,
            crs=feature.crs,
            properties=feature.properties,
            supported=feature.supported,
            area=feature.area,
            length=feature.length,
            unit=feature.unit,
            message=feature.message,
        )
        for feature in features
    ]

    return MeasurementsResponse(
        file_id=record.id,
        crs=record.crs or "",
        measurement_crs=record.measurement_crs or "",
        feature_count=record.feature_count,
        measurements=measurements,
    )