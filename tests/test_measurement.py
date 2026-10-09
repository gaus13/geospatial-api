"""Tests for CRS-aware geometry measurements."""

from math import isclose
from math import nan

import geopandas as gpd
import pytest
from shapely.geometry import (
    GeometryCollection,
    LineString,
    Point,
    Polygon,
)

from app.exceptions import FileProcessingError, MissingCRSError
from app.services.measurement import compute_measurements


def test_one_kilometre_square_has_expected_area() -> None:
    """A known 1 km by 1 km square should measure approximately 1 km²."""

    square = Polygon(
        [
            (500000, 1425000),
            (501000, 1425000),
            (501000, 1426000),
            (500000, 1426000),
        ]
    )

    projected = gpd.GeoDataFrame(
        {"name": ["square"]},
        geometry=[square],
        crs="EPSG:32643",
    )
    geographic = projected.to_crs("EPSG:4326")

    result = compute_measurements(geographic)
    feature = result.features[0]

    assert result.crs == "EPSG:4326"
    assert result.measurement_crs == "EPSG:32643"
    assert feature.geometry_type == "Polygon"
    assert feature.supported is True
    assert feature.unit == "square_meters"
    assert feature.area is not None
    assert isclose(feature.area, 1_000_000, rel_tol=0.005)


def test_linestring_length_is_returned_in_metres() -> None:
    """A LineString should return a length in metres."""

    line = LineString(
        [
            (0, 0),
            (1000, 0),
        ]
    )

    projected = gpd.GeoDataFrame(
        geometry=[line],
        crs="EPSG:32643",
    )
    geographic = projected.to_crs("EPSG:4326")

    result = compute_measurements(geographic)
    feature = result.features[0]

    assert feature.geometry_type == "LineString"
    assert feature.supported is True
    assert feature.unit == "meters"
    assert feature.length is not None
    assert isclose(feature.length, 1000, rel_tol=0.005)


def test_point_requires_no_measurement() -> None:
    """A Point is supported but does not require area or length."""

    gdf = gpd.GeoDataFrame(
        {"name": ["well"]},
        geometry=[Point(77.5, 12.9)],
        crs="EPSG:4326",
    )

    result = compute_measurements(gdf)
    feature = result.features[0]

    assert feature.geometry_type == "Point"
    assert feature.supported is True
    assert feature.area is None
    assert feature.length is None
    assert feature.unit is None
    assert feature.message == "No measurement required for Point."


def test_unsupported_geometry_does_not_crash() -> None:
    """Unsupported geometry types should return a clear result."""

    gdf = gpd.GeoDataFrame(
        geometry=[GeometryCollection([Point(77.5, 12.9)])],
        crs="EPSG:4326",
    )

    result = compute_measurements(gdf)
    feature = result.features[0]

    assert feature.geometry_type == "GeometryCollection"
    assert feature.supported is False
    assert feature.area is None
    assert feature.length is None
    assert "not supported" in (feature.message or "")


def test_empty_geometry_is_handled() -> None:
    """Empty geometries should not cause an exception."""

    gdf = gpd.GeoDataFrame(
        geometry=[Polygon()],
        crs="EPSG:4326",
    )

    result = compute_measurements(gdf)
    feature = result.features[0]

    assert feature.geometry_type is None
    assert feature.geometry is None
    assert feature.supported is False
    assert feature.message == "Empty or missing geometry."


def test_invalid_polygon_is_measured_with_warning() -> None:
    """An invalid polygon is measured but includes a warning."""

    invalid_polygon = Polygon(
        [
            (0, 0),
            (1000, 1000),
            (0, 1000),
            (1000, 0),
            (0, 0),
        ]
    )

    projected = gpd.GeoDataFrame(
        geometry=[invalid_polygon],
        crs="EPSG:32643",
    )
    geographic = projected.to_crs("EPSG:4326")

    result = compute_measurements(geographic)
    feature = result.features[0]

    assert feature.supported is True
    assert feature.area is not None
    assert feature.message == (
        "Geometry is invalid; measurement may be unreliable."
    )


def test_non_finite_measurement_is_returned_as_unsupported() -> None:
    """A non-finite area must not break JSON API serialization."""

    polygon_with_non_finite_coordinate = Polygon(
        [
            (0, 0),
            (1, 0),
            (nan, nan),
            (0, 0),
        ]
    )
    gdf = gpd.GeoDataFrame(
        geometry=[polygon_with_non_finite_coordinate],
        crs="EPSG:4326",
    )

    result = compute_measurements(gdf)
    feature = result.features[0]

    assert feature.supported is False
    assert feature.area is None
    assert feature.unit is None
    assert feature.message == (
        "Area could not be calculated because the geometry "
        "produced a non-finite measurement."
    )


def test_missing_crs_raises_error() -> None:
    """Data without a CRS must be rejected instead of measured incorrectly."""

    gdf = gpd.GeoDataFrame(
        geometry=[Point(77.5, 12.9)],
    )

    with pytest.raises(MissingCRSError):
        compute_measurements(gdf)


def test_empty_geodataframe_raises_error() -> None:
    """A file with zero features must be rejected."""

    gdf = gpd.GeoDataFrame(
        geometry=[],
        crs="EPSG:4326",
    )

    with pytest.raises(FileProcessingError, match="File contains no features"):
        compute_measurements(gdf)
