"""Shared pytest fixtures for geospatial file tests."""

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import geopandas as gpd
import pytest
from shapely.geometry import Polygon


@pytest.fixture
def sample_kml_path(tmp_path: Path) -> Path:
    """Create a small KML file containing polygon, line, and point features."""

    kml_content = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <Placemark>
      <name>Field A</name>
      <Polygon>
        <outerBoundaryIs>
          <LinearRing>
            <coordinates>
              77.5000,12.9000,0
              77.5100,12.9000,0
              77.5100,12.9100,0
              77.5000,12.9100,0
              77.5000,12.9000,0
            </coordinates>
          </LinearRing>
        </outerBoundaryIs>
      </Polygon>
    </Placemark>
    <Placemark>
      <name>Fence</name>
      <LineString>
        <coordinates>
          77.5000,12.9000,0
          77.5100,12.9100,0
        </coordinates>
      </LineString>
    </Placemark>
    <Placemark>
      <name>Well</name>
      <Point>
        <coordinates>77.5050,12.9050,0</coordinates>
      </Point>
    </Placemark>
  </Document>
</kml>
"""

    kml_path = tmp_path / "sample.kml"
    kml_path.write_text(kml_content, encoding="utf-8")
    return kml_path


@pytest.fixture
def sample_shapefile_zip(tmp_path: Path) -> Path:
    """Create a CRS-aware polygon Shapefile and package its files into a ZIP."""

    shapefile_directory = tmp_path / "shapefile"
    shapefile_directory.mkdir()

    shapefile_path = shapefile_directory / "sample.shp"

    geodataframe = gpd.GeoDataFrame(
        {"name": ["Field A"]},
        geometry=[
            Polygon(
                [
                    (77.5000, 12.9000),
                    (77.5100, 12.9000),
                    (77.5100, 12.9100),
                    (77.5000, 12.9100),
                    (77.5000, 12.9000),
                ]
            )
        ],
        crs="EPSG:4326",
    )

    geodataframe.to_file(
        shapefile_path,
        driver="ESRI Shapefile",
    )

    zip_path = tmp_path / "sample_shapefile.zip"

    with ZipFile(zip_path, "w", compression=ZIP_DEFLATED) as archive:
        for component_path in shapefile_directory.iterdir():
            archive.write(
                component_path,
                arcname=component_path.name,
            )

    return zip_path