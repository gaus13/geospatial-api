# This will contain shared status values, allowed extensions, and archive limits.

STATUS_PROCESSING = "PROCESSING"
STATUS_COMPLETED = "COMPLETED"
STATUS_FAILED = "FAILED"

# File extensions accepted by the upload endpoint.
ALLOWED_EXTENSIONS = {".kml", ".zip"}

# ZIP archive safety limits.
MAX_ZIP_MEMBERS = 500
MAX_ZIP_UNCOMPRESSED_BYTES = 200 * 1024 * 1024

