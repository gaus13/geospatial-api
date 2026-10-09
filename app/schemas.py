# What this file does:
# This will define Pydantic request and response models for uploads, file
# information, feature measurements, and error payloads.
#
# Why it is needed:
# Explicit schemas validate API output, document the contract in /docs, and
# prevent accidental response-shape changes.

from __future__ import annotations
from typing import Any
from pydantic import BaseModel, ConfigDict

class FileResponse(BaseModel):
    """Response returned after a file is uploaded or retrieved."""
    id: str
    filename: str
    feature_count: int
    crs: str | None
    status: str
    error_message: str | None = None

    model_config = ConfigDict(from_attributes=True)


class FeatureMeasurementResponse(BaseModel):
    """Measurement information for one geospatial feature."""

    index: int
    geometry_type: str | None
    geometry: dict[str, Any] | None
    crs: str
    properties: dict[str, Any]
    supported: bool
    area: float | None = None
    length: float | None = None
    unit: str | None = None
    message: str | None = None    

class MeasurementsResponse(BaseModel):
    """Response containing all measurements for one uploaded file."""

    file_id: str
    crs: str
    measurement_crs: str
    feature_count: int
    measurements: list[FeatureMeasurementResponse]    