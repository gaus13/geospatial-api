# What this file does:
# This will define the files and features SQLAlchemy/GeoAlchemy2 models,
# including the PostGIS geometry column and indexes.
#
# Why it is needed:
# Persistent file and feature records allow later API requests to retrieve
# processing status, metadata, measurements, and spatial data.

"""SQLAlchemy and GeoAlchemy2 database models."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from geoalchemy2 import Geometry
from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class FileRecord(Base):
    """Database record representing one uploaded geospatial file."""

    __tablename__ = "files"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_path: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    feature_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    crs: Mapped[str | None] = mapped_column(String(100), nullable=True)
    measurement_crs: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    features: Mapped[list[FeatureRecord]] = relationship(
        back_populates="file",
        cascade="all, delete-orphan",
    )


class FeatureRecord(Base):
    """Database record representing one feature in an uploaded file."""

    __tablename__ = "features"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    file_id: Mapped[str] = mapped_column(
        ForeignKey("files.id", ondelete="CASCADE"),
        nullable=False,
    )
    feature_index: Mapped[int] = mapped_column(Integer, nullable=False)
    geometry_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )
    geometry: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
    )
    geom: Mapped[Any | None] = mapped_column(
        Geometry(
            geometry_type="GEOMETRY",
            srid=4326,
            spatial_index=True,
        ),
        nullable=True,
    )
    crs: Mapped[str] = mapped_column(String(100), nullable=False)
    properties: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )
    supported: Mapped[bool] = mapped_column(nullable=False)
    area: Mapped[float | None] = mapped_column(Float, nullable=True)
    length: Mapped[float | None] = mapped_column(Float, nullable=True)
    unit: Mapped[str | None] = mapped_column(String(30), nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)

    file: Mapped[FileRecord] = relationship(back_populates="features")


Index("ix_features_file_id", FeatureRecord.file_id)


    