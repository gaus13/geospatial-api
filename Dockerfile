# What this file does:
# This will describe how to build the production-like container for the API.
#
# Why it is needed:
# Docker gives reviewers a consistent Python and GDAL environment for running
# the service without manually installing geospatial system dependencies.

# Use Python 3.12 with a small Linux base image.
FROM python:3.12-slim

# Prevent Python from creating .pyc files and enable immediate logs.
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system libraries needed by GeoPandas, PyProj, Shapely, and Pyogrio.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        gdal-bin \
        libgdal-dev \
        libgeos-dev \
        libproj-dev \
    && rm -rf /var/lib/apt/lists/*

# Use /app as the container working directory.
WORKDIR /app

# Copy dependencies first so Docker can reuse this build layer.
COPY requirements.txt .

# Install Python dependencies without keeping pip's cache.
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application source and configuration files.
COPY app ./app
COPY .env.example ./.env.example

# Create the directory used for uploaded files.
RUN mkdir -p /app/uploads

# Make the API available on port 8000.
EXPOSE 8000

# Start the FastAPI application.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]