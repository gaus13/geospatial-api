"""Shared pytest fixtures for geospatial file tests."""

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import geopandas as gpd
import pytest
from shapely.geometry import Polygon

from collections.abc import Generator

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.db import Base, get_db
from app.main import app


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


@pytest.fixture
def test_database() -> Generator[Session, None, None]:
    """Provide a clean PostgreSQL/PostGIS test database session."""

    engine = create_engine(settings.test_database_url)

    with engine.begin() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))

    Base.metadata.create_all(bind=engine)

    test_session_factory = sessionmaker(
        bind=engine,
        autocommit=False,
        autoflush=False,
    )

    database = test_session_factory()

    try:
        yield database
    finally:
        database.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture
def client(
    test_database: Session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[TestClient, None, None]:
    """Provide an API client connected to the isolated test database."""

    def override_get_db() -> Generator[Session, None, None]:
        yield test_database

    app.dependency_overrides[get_db] = override_get_db
    monkeypatch.setattr(settings, "upload_dir", tmp_path / "uploads")

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()