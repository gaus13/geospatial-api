"""Measurement service placeholder."""

# What this file does:
# This will implement pure CRS-aware area and length calculations for every
# feature in a GeoDataFrame.
#
# Why it is needed:
# Measurement is the central geospatial requirement and must be independently
# testable without FastAPI or database dependencies.

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import geopandas as gpd
from shapely import force_2d

from app.exceptions import FileProcessingError, MissingCRSError

@dataclass(frozen=True)
class FeatureResult:
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


@dataclass(frozen=True)
class MeasurementResult:
    """Measurement results for an entire GeoDataFrame."""

    crs: str
    measurement_crs: str
    features: list[FeatureResult]  

def _crs_label(crs: Any) -> str:
    """Return a stable label such as EPSG:4326 for a CRS."""
    epsg = crs.to_epsg()

    if epsg is not None:
        return f"EPSG:{epsg}"

    return str(crs.name or crs)


def compute_measurements(gdf: gpd.GeoDataFrame) -> MeasurementResult:
    """Calculate metric measurements for features in a GeoDataFrame."""

    if gdf.crs is None:
        raise MissingCRSError("Input data has no coordiante reference system.")

    if gdf.empty:
        raise FileProcessingError("File contains no features.")

    source_crs = _crs_label(gdf.crs)

    # Normalize the data to longitude/latitude before selecting a UTM zone.
    geographic = gdf.to_crs("EPSG:4326")

    # Select a local projected CRS whose units are metres.
    metric_crs = geographic.estimate_utm_crs()

    if metric_crs is None:
        raise FileProcessingError(
            "Unable to select a projected CRS for measurement."
        )
    
    metric = gdf.to_crs(metric_crs)
    measurement_crs = _crs_label(metric_crs)

    # This creates JSON-safe geometries and properties for API responses.
    source_features = json.loads(gdf.to_json(drop_id=True))["features"]

    results: list[FeatureResult] = []

    for index, (source_row, metric_row, source_feature) in enumerate(
        zip(
            gdf.itertuples(index=False),
            metric.itertuples(index=False),
            source_features,
        )
    ):
        geometry = source_row.geometry
        metric_geometry = metric_row.geometry

        geometry_json = source_feature.get("geometry")
        properties = source_feature.get("properties") or {}

        if geometry is None or geometry.is_empty:
            results.append(
                FeatureResult(
                    index=index,
                    geometry_type=None,
                    geometry=None,
                    crs=source_crs,
                    properties=properties,
                    supported=False,
                    message="Empty or missing geometry.",
                )
            )
            continue

        geometry_type = geometry.geom_type

        warning = None
        if not geometry.is_valid:
            warning = "Geometry is invalid; measurement may be unreliable."

        if geometry_type in {"Polygon", "MultiPolygon"}:
            results.append(
                FeatureResult(
                    index=index,
                    geometry_type=geometry_type,
                    geometry=geometry_json,
                    crs=source_crs,
                    properties=properties,
                    supported=True,
                    area=round(force_2d(metric_geometry).area, 2),
                    unit="square_meters",
                    message=warning,
                )
            )

        elif geometry_type in {"LineString", "MultiLineString"}:
            results.append(
                FeatureResult(
                    index=index,
                    geometry_type=geometry_type,
                    geometry=geometry_json,
                    crs=source_crs,
                    properties=properties,
                    supported=True,
                    length=round(force_2d(metric_geometry).length, 2),
                    unit="meters",
                    message=warning,
                )
            )    

        elif geometry_type in {"Point", "MultiPoint"}:
            results.append(
                FeatureResult(
                    index=index,
                    geometry_type=geometry_type,
                    geometry=geometry_json,
                    crs=source_crs,
                    properties=properties,
                    supported=True,
                    message="No measurement required for Point.",
                )
            )    

        else:
            results.append(
                FeatureResult(
                    index=index,
                    geometry_type=geometry_type,
                    geometry=geometry_json,
                    crs=source_crs,
                    properties=properties,
                    supported=False,
                    message=(
                        f"Geometry type '{geometry_type}' is not supported "
                        "for measurement."
                    ),
                )
            )
    return MeasurementResult(
        crs=source_crs,
        measurement_crs=measurement_crs,
        features=results,
    )