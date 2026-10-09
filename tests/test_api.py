# What this file does:
# This will test all required endpoints, response shapes, status codes, failed
# processing records, and PostGIS persistence.
#
# Why it is needed:
# End-to-end tests verify that the individual services work together through the
# public API contract.

"""Tests for the public file API endpoints."""

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from fastapi.testclient import TestClient

from app.config import settings


def test_upload_kml_returns_completed_file(
    client: TestClient,
    sample_kml_path: Path,
) -> None:
    """A valid KML upload should be processed and persisted."""

    with sample_kml_path.open("rb") as file:
        response = client.post(
            "/api/files/",
            files={
                "file": (
                    sample_kml_path.name,
                    file,
                    "application/vnd.google-earth.kml+xml",
                )
            },
        )

    assert response.status_code == 201

    body = response.json()

    assert body["filename"] == "sample.kml"
    assert body["status"] == "COMPLETED"
    assert body["feature_count"] == 3
    assert body["crs"] == "EPSG:4326"
    assert body["error_message"] is None
    assert body["id"]


def test_get_file_returns_uploaded_file(
    client: TestClient,
    sample_kml_path: Path,
) -> None:
    """A completed file should be retrievable by its ID."""

    with sample_kml_path.open("rb") as file:
        upload_response = client.post(
            "/api/files/",
            files={"file": (sample_kml_path.name, file)},
        )

    file_id = upload_response.json()["id"]

    response = client.get(f"/api/files/{file_id}/")

    assert response.status_code == 200
    assert response.json()["id"] == file_id
    assert response.json()["status"] == "COMPLETED"


def test_get_measurements_returns_all_features(
    client: TestClient,
    sample_kml_path: Path,
) -> None:
    """The measurements endpoint should return every parsed feature."""

    with sample_kml_path.open("rb") as file:
        upload_response = client.post(
            "/api/files/",
            files={"file": (sample_kml_path.name, file)},
        )

    file_id = upload_response.json()["id"]

    response = client.get(
        f"/api/files/{file_id}/measurements/"
    )

    assert response.status_code == 200

    body = response.json()

    assert body["file_id"] == file_id
    assert body["feature_count"] == 3
    assert len(body["measurements"]) == 3
    assert body["measurement_crs"].startswith("EPSG:")

    geometry_types = [
        measurement["geometry_type"]
        for measurement in body["measurements"]
    ]

    assert geometry_types == ["Polygon", "LineString", "Point"]


def test_unknown_file_returns_404(client: TestClient) -> None:
    """An unknown UUID should return the required 404 response."""

    response = client.get(
        "/api/files/00000000-0000-0000-0000-000000000000/"
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "File not found."


def test_invalid_file_type_returns_400(client: TestClient) -> None:
    """Unsupported extensions should be rejected before processing."""

    response = client.post(
        "/api/files/",
        files={
            "file": (
                "notes.txt",
                b"not a geospatial file",
                "text/plain",
            )
        },
    )

    assert response.status_code == 400
    assert "Unsupported file type" in response.json()["detail"]


def test_empty_file_returns_400(client: TestClient) -> None:
    """An empty upload should return the required 400 response."""

    response = client.post(
        "/api/files/",
        files={
            "file": (
                "empty.kml",
                b"",
                "application/vnd.google-earth.kml+xml",
            )
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Uploaded file is empty."


def test_corrupt_zip_returns_failed_record(client: TestClient) -> None:
    """A corrupt ZIP should create a FAILED database record."""

    response = client.post(
        "/api/files/",
        files={
            "file": (
                "broken.zip",
                b"this is not a valid zip file",
                "application/zip",
            )
        },
    )

    assert response.status_code == 422

    body = response.json()

    assert body["detail"]["detail"] == (
        "Uploaded ZIP archive is corrupt."
    )
    assert body["detail"]["status"] == "FAILED"
    assert body["detail"]["id"]


def test_zip_without_shapefile_returns_failed_record(
    client: TestClient,
    tmp_path: Path,
) -> None:
    """A ZIP without a Shapefile should be rejected with FAILED status."""

    zip_path = tmp_path / "no_shapefile.zip"

    import zipfile

    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr("readme.txt", "not a shapefile")

    with zip_path.open("rb") as file:
        response = client.post(
            "/api/files/",
            files={
                "file": (
                    zip_path.name,
                    file,
                    "application/zip",
                )
            },
        )

    assert response.status_code == 422

    body = response.json()

    assert "does not contain a Shapefile" in body["detail"]["detail"]
    assert body["detail"]["status"] == "FAILED"
    assert body["detail"]["id"]


def test_upload_shapefile_zip_returns_completed_file(
    client: TestClient,
    sample_shapefile_zip: Path,
) -> None:
    """A valid zipped Shapefile should be processed and measured."""

    with sample_shapefile_zip.open("rb") as file:
        response = client.post(
            "/api/files/",
            files={
                "file": (
                    sample_shapefile_zip.name,
                    file,
                    "application/zip",
                )
            },
        )

    assert response.status_code == 201

    body = response.json()

    assert body["filename"] == "sample_shapefile.zip"
    assert body["status"] == "COMPLETED"
    assert body["feature_count"] == 1
    assert body["crs"] == "EPSG:4326"
    assert body["id"]

    measurements_response = client.get(
        f"/api/files/{body['id']}/measurements/"
    )

    assert measurements_response.status_code == 200

    measurement = measurements_response.json()["measurements"][0]

    assert measurement["geometry_type"] == "Polygon"
    assert measurement["area"] is not None
    assert measurement["area"] > 0
    assert measurement["unit"] == "square_meters"


def test_shapefile_without_prj_returns_failed_record(
    client: TestClient,
    sample_shapefile_zip: Path,
    tmp_path: Path,
) -> None:
    """A Shapefile without its CRS file should return FAILED status."""

    zip_path = tmp_path / "missing-prj.zip"

    with ZipFile(zip_path, "w", compression=ZIP_DEFLATED) as output:
        with ZipFile(sample_shapefile_zip) as source:
            for item in source.infolist():
                if not item.filename.lower().endswith(".prj"):
                    output.writestr(item.filename, source.read(item.filename))

    with zip_path.open("rb") as file:
        response = client.post(
            "/api/files/",
            files={"file": (zip_path.name, file, "application/zip")},
        )

    assert response.status_code == 422
    body = response.json()["detail"]
    assert body["status"] == "FAILED"
    assert body["id"]
    assert body["detail"] == "Shapefile has no CRS (.prj file missing)."


def test_multiple_shapefiles_returns_failed_record(
    client: TestClient,
    sample_shapefile_zip: Path,
    tmp_path: Path,
) -> None:
    """An archive with multiple Shapefiles should return FAILED status."""

    zip_path = tmp_path / "multiple-shapefiles.zip"

    with ZipFile(zip_path, "w", compression=ZIP_DEFLATED) as output:
        with ZipFile(sample_shapefile_zip) as source:
            for item in source.infolist():
                output.writestr(item.filename, source.read(item.filename))
        output.writestr("second.shp", b"not a valid Shapefile")

    with zip_path.open("rb") as file:
        response = client.post(
            "/api/files/",
            files={"file": (zip_path.name, file, "application/zip")},
        )

    assert response.status_code == 422
    body = response.json()["detail"]
    assert body["status"] == "FAILED"
    assert "exactly one Shapefile" in body["detail"]


def test_unsafe_zip_path_returns_failed_record(client: TestClient) -> None:
    """An archive attempting path traversal should return FAILED status."""

    response = client.post(
        "/api/files/",
        files={
            "file": (
                "unsafe.zip",
                _zip_bytes({"../outside.txt": b"unsafe content"}),
                "application/zip",
            )
        },
    )

    assert response.status_code == 422
    body = response.json()["detail"]
    assert body["status"] == "FAILED"
    assert body["detail"] == "ZIP archive contains an unsafe path."


def _zip_bytes(files: dict[str, bytes]) -> bytes:
    """Build an in-memory ZIP archive for API security tests."""

    from io import BytesIO

    buffer = BytesIO()
    with ZipFile(buffer, "w", compression=ZIP_DEFLATED) as archive:
        for filename, content in files.items():
            archive.writestr(filename, content)
    return buffer.getvalue()


def test_missing_file_field_returns_400(client: TestClient) -> None:
    """A request without the required file field should return 400."""

    response = client.post("/api/files/", data={"wrong_field": "value"})

    assert response.status_code == 400
    assert "Unsupported file type" in response.json()["detail"]


def test_oversized_upload_returns_413(
    client: TestClient,
    monkeypatch,
) -> None:
    """An upload exceeding the configured limit should return 413."""

    monkeypatch.setattr(settings, "max_upload_mb", 0)

    response = client.post(
        "/api/files/",
        files={"file": ("large.kml", b"not empty", "text/plain")},
    )

    assert response.status_code == 413
    assert "File is too large" in response.json()["detail"]


def test_empty_zip_returns_failed_record(client: TestClient) -> None:
    """An empty ZIP should be rejected and recorded as FAILED."""

    response = client.post(
        "/api/files/",
        files={
            "file": (
                "empty.zip",
                _zip_bytes({}),
                "application/zip",
            )
        },
    )

    assert response.status_code == 422
    body = response.json()["detail"]
    assert body["status"] == "FAILED"
    assert body["id"]
    assert "does not contain a Shapefile" in body["detail"]


def test_failed_file_can_be_retrieved(
    client: TestClient,
) -> None:
    """A failed upload should remain available through the file endpoint."""

    response = client.post(
        "/api/files/",
        files={
            "file": (
                "broken.zip",
                b"not a valid ZIP",
                "application/zip",
            )
        },
    )

    assert response.status_code == 422
    failed_id = response.json()["detail"]["id"]

    lookup_response = client.get(f"/api/files/{failed_id}/")

    assert lookup_response.status_code == 200
    body = lookup_response.json()
    assert body["id"] == failed_id
    assert body["status"] == "FAILED"
    assert body["error_message"] == "Uploaded ZIP archive is corrupt."