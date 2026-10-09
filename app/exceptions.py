"""Application exception placeholder."""

# What this file does:
# This will define clear domain exceptions for invalid uploads, missing CRS,
# unsupported files, and processing failures.
#
# Why it is needed:
# The API must convert expected processing problems into precise JSON responses
# instead of exposing implementation errors or returning unexplained crashes.

class FileProcessingError(Exception):

    def __init__(
        self,
        message: str,
        file_id: str | None = None,
    ) -> None:
        self.message = message
        self.file_id = file_id
        super().__init__(message)
        

class MissingCRSError(FileProcessingError):
    """Raised when an input file does not contain a coordinate reference system."""


class UnsupportedFileError(FileProcessingError):
    """Raised when an uploaded file or archive is not supported."""       

