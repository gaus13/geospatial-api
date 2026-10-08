"""Parser and storage test placeholder."""

# What this file does:
# This will test KML/Shapefile parsing, missing CRS handling, archive validation,
# zip-slip prevention, and ZIP bomb limits.
#
# Why it is needed:
# Parser and upload failures must be safe, predictable, and clearly reported.

# temporary test
"""def test_fixtures_create_files(sample_kml_path, sample_shapefile_zip):
    assert sample_kml_path.exists()
    assert sample_kml_path.suffix == ".kml"

    assert sample_shapefile_zip.exists()
    assert sample_shapefile_zip.suffix == ".zip"""

"""Tests for geospatial file parsing and archive validation."""

"""Tests for geospatial file parsing and archive validation."""

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import geopandas as gpd
import pytest

from app.exceptions import FileProcessingError, MissingCRSError
from app.services.parser import parse_geospatial_file


def test_kml_file_is_parsed(sample_kml_path: Path, tmp_path: Path) -> None:
    """A valid KML should load with its features and CRS."""

    result = parse_geospatial_file(
        sample_kml_path,
        tmp_path / "kml-extracted",
    )

    assert len(result) == 3
    assert result.crs.to_epsg() == 4326
    assert set(result.geometry.geom_type) == {
        "Polygon",
        "LineString",
        "Point",
    }
    assert "Name" in result.columns


def test_shapefile_zip_is_parsed(
    sample_shapefile_zip: Path,
    tmp_path: Path,
) -> None:
    """A valid Shapefile ZIP should load with its CRS."""

    result = parse_geospatial_file(
        sample_shapefile_zip,
        tmp_path / "shapefile-extracted",
    )

    assert len(result) == 1
    assert result.crs.to_epsg() == 4326
    assert result.geometry.iloc[0].geom_type == "Polygon"
    assert result.iloc[0]["name"] == "Field A"


def test_zip_without_shapefile_is_rejected(tmp_path: Path) -> None:
    """An archive without a .shp file should be rejected."""

    zip_path = tmp_path / "missing-shapefile.zip"

    with ZipFile(zip_path, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("readme.txt", "not a shapefile")

    with pytest.raises(
        FileProcessingError,
        match="does not contain a Shapefile",
    ):
        parse_geospatial_file(zip_path, tmp_path / "extracted")


def test_zip_with_multiple_shapefiles_is_rejected(
    sample_shapefile_zip: Path,
    tmp_path: Path,
) -> None:
    """An archive with more than one .shp file should be rejected."""

    zip_path = tmp_path / "multiple-shapefiles.zip"

    with ZipFile(zip_path, "w", compression=ZIP_DEFLATED) as output:
        with ZipFile(sample_shapefile_zip) as source:
            for item in source.infolist():
                output.writestr(item.filename, source.read(item.filename))

        output.writestr("second.shp", b"fake shapefile")

    with pytest.raises(
        FileProcessingError,
        match="exactly one Shapefile",
    ):
        parse_geospatial_file(zip_path, tmp_path / "extracted")


def test_shapefile_without_prj_is_rejected(
    sample_shapefile_zip: Path,
    tmp_path: Path,
) -> None:
    """A Shapefile archive without .prj must be rejected."""

    zip_path = tmp_path / "missing-prj.zip"

    with ZipFile(zip_path, "w", compression=ZIP_DEFLATED) as output:
        with ZipFile(sample_shapefile_zip) as source:
            for item in source.infolist():
                if item.filename.lower().endswith(".prj"):
                    continue

                output.writestr(item.filename, source.read(item.filename))

    with pytest.raises(
        MissingCRSError,
        match=r"\.prj file missing",
    ):
        parse_geospatial_file(zip_path, tmp_path / "extracted")


def test_zip_slip_path_is_rejected(tmp_path: Path) -> None:
    """An archive attempting to escape extraction should be rejected."""

    zip_path = tmp_path / "zip-slip.zip"

    with ZipFile(zip_path, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("../outside.txt", "unsafe content")

    with pytest.raises(
        FileProcessingError,
        match="unsafe path",
    ):
        parse_geospatial_file(zip_path, tmp_path / "extracted")