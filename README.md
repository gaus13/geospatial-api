# Geospatial File Measurement API

FastAPI service for uploading **KML files** and **zipped Shapefiles**, extracting their features, calculating CRS-aware measurements, and storing the results in **PostgreSQL/PostGIS**.

## Quick start with Docker

### Prerequisites

- Docker Desktop
- Git
- Python 3.11+ for running tests locally

### Start the complete application

```powershell
git clone https://github.com/gaus13/geospatial-api.git
cd geospatial-api
Copy-Item .env.example .env
docker compose up --build
```

Docker Compose starts:

- `db`: PostgreSQL 16 with PostGIS 3.4
- `api`: FastAPI running with Uvicorn

Open the interactive API documentation:

```text
http://127.0.0.1:8000/docs
```

Check the services:

```powershell
docker compose ps
```

The database should be `healthy` and the API should be running.

Stop the application:

```powershell
docker compose down
```

The database is exposed to the host on port `5433`. Inside Docker Compose, the API connects to the database using the hostname `db` and port `5432`.

## Local development

Docker is still required because the project uses PostgreSQL/PostGIS.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
docker compose up -d db
python -m uvicorn app.main:app --reload
```

The local API is available at `http://127.0.0.1:8000`.

## API

All endpoints use the `/api` base path. Full request and response schemas are available at `/docs`.

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/api/files/` | Upload and process a KML or zipped Shapefile |
| `GET` | `/api/files/{file_id}/` | Retrieve file information and status |
| `GET` | `/api/files/{file_id}/measurements/` | Retrieve per-feature measurements |

### Upload example

```powershell
curl.exe -X POST "http://127.0.0.1:8000/api/files/" `
  -F "file=@sample-data/sample-map.kml"
```

Successful uploads return `201 Created`:

```json
{
  "id": "file-uuid",
  "filename": "sample-map.kml",
  "feature_count": 167,
  "crs": "EPSG:4326",
  "status": "COMPLETED",
  "error_message": null
}
```

Use the returned ID with the two `GET` endpoints.

### Measurement behavior

```json
{
  "file_id": "file-uuid",
  "crs": "EPSG:4326",
  "measurement_crs": "EPSG:32643",
  "feature_count": 3,
  "measurements": [
    {
      "index": 0,
      "geometry_type": "Polygon",
      "supported": true,
      "area": 12345.67,
      "length": null,
      "unit": "square_meters"
    },
    {
      "index": 1,
      "geometry_type": "LineString",
      "supported": true,
      "area": null,
      "length": 1612.87,
      "unit": "meters"
    },
    {
      "index": 2,
      "geometry_type": "Point",
      "supported": true,
      "area": null,
      "length": null,
      "unit": null,
      "message": "No measurement required for Point."
    }
  ]
}
```

### Error handling

| Situation | Status |
|---|---:|
| Missing file, unsupported extension, or empty upload | `400` |
| Upload exceeds `MAX_UPLOAD_MB` | `413` |
| Corrupt ZIP, invalid Shapefile, missing CRS, or zero features | `422` |
| Unknown file ID | `404` |
| Invalid UUID format | `422` |

Processing failures are saved with `status: "FAILED"` and an `error_message`, so the failed record can still be retrieved.

## Architecture

```text
app/
├── api/files.py                 # HTTP routes
├── services/
│   ├── file_service.py          # Processing orchestration
│   ├── parser.py                # KML and Shapefile parsing
│   ├── measurement.py           # CRS-aware measurement logic
│   └── storage.py               # Upload validation and safe storage
├── config.py                    # Environment settings
├── db.py                        # Database sessions
├── models.py                    # SQLAlchemy/PostGIS models
├── schemas.py                   # API response schemas
└── main.py                      # FastAPI application
```

Routes only handle HTTP concerns. Parsing, measurements, storage, and persistence are kept in separate services so they can be tested independently.

## CRS and geospatial decisions

KML commonly uses `EPSG:4326`, which stores longitude and latitude in degrees. Degrees are not valid units for reliable area or length calculations.

The application:

1. Reads the source CRS.
2. Normalizes geometry to `EPSG:4326`.
3. Estimates a local UTM projected CRS.
4. Reprojects geometry to that metric CRS.
5. Calculates area in square metres or length in metres.
6. Stores the original CRS and measurement CRS in the response.

Supported measurements:

- `Polygon` and `MultiPolygon`: area in `square_meters`
- `LineString` and `MultiLineString`: length in `meters`
- `Point` and `MultiPoint`: no measurement required
- Empty or unsupported geometries: clear explanatory response

Feature geometries are stored in PostGIS as `EPSG:4326` geometry, with spatial indexing for future spatial queries.

## Upload safety

- Uploads are streamed in chunks and limited by `MAX_UPLOAD_MB`.
- Files are stored under UUID-generated directories.
- User filenames are never used as storage paths.
- ZIP path traversal is rejected.
- ZIP member count and uncompressed size are limited.
- Exactly one Shapefile is required.
- Shapefiles must include `.shp`, `.shx`, `.dbf`, and `.prj`.

## Testing

Run the test suite with:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Tests cover:

- KML and zipped Shapefile uploads
- File and measurement retrieval
- CRS-aware area and length calculations
- Empty, oversized, corrupt, and unsupported uploads
- Missing or multiple Shapefiles
- Missing `.prj` files
- ZIP path traversal
- Failed-record persistence and retrieval
- PostgreSQL/PostGIS-backed API behavior

## Evidence for reviewers

After running the project, capture these concise screenshots:

1. `docker compose ps` showing the API and healthy database.
2. Swagger UI showing the three API endpoints.
3. Successful upload response with `COMPLETED` status.
4. Measurements response showing `measurement_crs`, area, length, and point handling.
5. Passing `pytest -q` output.

Store optional screenshots in:

```text
docs/screenshots/
```

Do not include `.env` contents, passwords, or private machine paths.

## Learning and future scope

This project provided practical experience with FastAPI, multipart uploads, GeoPandas, Shapely, CRS transformations, PostGIS, Docker Compose, layered architecture, and API testing.

Possible future improvements include background processing for large files, authentication, pagination, Alembic migrations, additional formats such as GeoJSON, spatial filtering, and production observability.
