# What this file does:
# This will validate archive contents and read KML or Shapefile data into a
# GeoPandas GeoDataFrame.
#
# Why it is needed:
# Parsing is format-specific and must consistently provide CRS, geometry, and
# properties to the measurement service.

"""Read supported geospatial files into GeoDataFrames."""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd

from app.exceptions import FileProcessingError, MissingCRSError
from app.services.storage import extract_zip_safely

def _find_shapefile(extracted_directory: Path) -> Path:
    """Find exactly one Shapefile while ignoring macOS metadata folders."""

    shapefiles = [
        Path
        for path in extracted_directory.rglob("*.shp")
        if "_MACOSX" not in path.parts
    ]

    if not shapefiles:
        raise FileProcessingError("ZIP archive does not contain a Shapefile.")

    if len(shapefiles) > 1:
        raise FileProcessingError("ZIP archive must contain exactly one Shapefile.")

    return shapefiles[0]

def _read_kml(file_path: Path) -> gpd.GeoDataFrame:
    """Read a KML file and ensure it has the KML CRS."""
    try:
        geodataframe = gpd.read_file(file_path, driver = "KML")

    except Exception as error:
        raise FileProcessingError("Unable to read KML file.") from error

    if geodataframe.crs is None:
        geodataframe = geodataframe.set_crs("EPSG:4326")

    return geodataframe


def _read_shapefile(
    file_path: Path,
    extraction_directory: Path,
) -> gpd.GeoDataFrame:
    """Read a Shapefile after validating its CRS sidecar file."""

    shapefile_path = _find_shapefile(extraction_directory)
    projection_path = shapefile_path.with_suffix(".prj")

    if not projection_path.exists():
        raise MissingCRSError(
            "Shapefile has no CRS (.prj file missing)."
        )
    try:
        geodataframe = gpd.read_file(shapefile_path)
    except Exception as error:
        raise FileProcessingError(
            "Unable to read Shapefile."
        ) from error

    if geodataframe.crs is None:
        raise MissingCRSError(
            "Shapefile has no CRS (.prj file missing)."
        )

    return geodataframe


def parse_geospatial_file(
    file_path: Path,
    extraction_directory: Path | None = None,
) -> gpd.GeoDataFrame:
    """Read a KML or zipped Shapefile into a GeoDataFrame."""

    extension = file_path.suffix.lower()

    if extension == ".kml":
        geodataframe = _read_kml(file_path)

    elif extension == ".zip":
        if extraction_directory is None:
            raise FileProcessingError(
                "An extraction directory is required for ZIP files."
            )

        extracted_directory = extract_zip_safely(
            file_path,
            extraction_directory,
        )
        geodataframe = _read_shapefile(
            file_path,
            extracted_directory,
        )

    else:
        raise FileProcessingError(
            "Unsupported file type. Upload a .kml or a .zip containing a Shapefile."
        )

    if geodataframe.empty:
        raise FileProcessingError("File contains no features.")

    if geodataframe.crs is None:
        raise MissingCRSError(
            "Input data has no coordinate reference system."
        )

    return geodataframe