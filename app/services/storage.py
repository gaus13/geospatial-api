# What this file does:
# This will save uploads safely, enforce size limits, create per-file
# directories, and extract ZIP archives without zip-slip vulnerabilities.
#
# Why it is needed:
# File handling is an input-security boundary and must be isolated from parsing
# and database code.
from __future__ import annotations

from pathlib import Path
from uuid import UUID
from zipfile import BadZipFile, ZipFile

from fastapi import UploadFile

from app.config import settings
from app.constants import (
    ALLOWED_EXTENSIONS,
    MAX_ZIP_MEMBERS,
    MAX_ZIP_UNCOMPRESSED_BYTES,
)
from app.exceptions import FileProcessingError, UnsupportedFileError

def get_upload_directory(file_id: UUID) -> Path:
    """Return and create the directory for one uploaded file."""
    directory = settings.upload_dir / str(file_id)
    directory.mkdir(parents=True, exist_ok=True)
    return directory

async def save_upload(upload: UploadFile, file_id: UUID) -> Path:
    """Save an uploaded file while enforcing extension and size limits."""

    filename = upload.filename or ""
    extension = Path(filename).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise UnsupportedFileError("Unsupported file type. Upload a .kml or a .zip containing a Shapefile.")

    upload_directory = get_upload_directory(file_id)
    destination = upload_directory / f"original{extension}"
    maximum_bytes = settings.max_upload_mb * 1024 * 1024
    total_bytes = 0

    try: 
        with destination.open("wb") as output_file:
            while chunk := await upload.read(1024*1024):
                total_bytes += len(chunk)

            if total_bytes > maximum_bytes:
                destination.unlink(missing_ok=True)
                raise FileProcessingError(
                    f"File is too large. Maximum size is "
                    f"{settings.max_upload_mb} MB"
                )  
              
                output_file.write(chunk)

    finally:
        await upload.close()

    if total_bytes == 0:
        destination.unlink(missing_ok=True)
        raise FileProcessingError("Uploaded file is empty")            

    return destination

def extract_zip_safely(zip_path: Path, destination: Path) -> Path:
    """Extract a Shapefile archive while blocking unsafe ZIP contents."""

    destination.mkdir(parents=True, exist_ok=True)

    try:
        with ZipFile(zip_path) as archive:
            members = archive.infolist()

            if len(members) > MAX_ZIP_MEMBERS:
                raise FileProcessingError(
                    f"ZIP archive contains more than {MAX_ZIP_MEMBERS} members."
                )

            uncompressed_size = sum(member.file_size for member in members)

            if uncompressed_size > MAX_ZIP_UNCOMPRESSED_BYTES:
                raise FileProcessingError(
                    "ZIP archive exceeds the maximum uncompressed size."
                )

            target_root = destination.resolve()

            for member in members:
                member_path = (destination / member.filename).resolve()

                if not member_path.is_relative_to(target_root):
                    raise FileProcessingError(
                        "ZIP archive contains an unsafe path."
                    )

            archive.extractall(destination)

    except BadZipFile as error:
        raise FileProcessingError("Uploaded ZIP archive is corrupt.") from error

    return destination