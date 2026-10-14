# Release builds should pin this base image by digest.
FROM python:3.11-slim

WORKDIR /app

# Copy package metadata first for layer caching
COPY pyproject.toml README.md LICENSE ./

# Copy source
COPY seraph/      ./seraph/
COPY adapters/    ./adapters/
COPY seraph_demo/ ./seraph_demo/
COPY validation/  ./validation/

# Install kernel + serve dependencies
RUN pip install --no-cache-dir ".[serve]"

EXPOSE 8000

# Bind to all interfaces so Docker port mapping works
CMD ["seraph-serve", "--host", "0.0.0.0", "--port", "8000"]
