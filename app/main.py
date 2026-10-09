# What this file does:
# This will create the FastAPI application, register routers, and configure
# startup tasks such as database initialization.
#
# Why it is needed:
# Uvicorn needs a stable application entry point, and all API requests need one
# configured FastAPI instance.

"""FastAPI application entry point."""

from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI

from app.api.files import router as files_router
from app.db import initialize_database


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncGenerator[None, None]:
    """Initialize application resources when the server starts."""

    initialize_database()
    yield


app = FastAPI(
    title="Geospatial File Measurement API",
    description=(
        "Upload KML and zipped Shapefiles and calculate "
        "CRS-aware geometry measurements."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(files_router)
