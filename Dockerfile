FROM python:3.11-slim-bookworm

WORKDIR /app

# Install system dependencies (minimal)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md LICENSE ./
COPY src/ src/

RUN pip install --no-cache-dir -e ".[plot]"

# Create data directory
RUN mkdir -p /root/.turbulence/data

VOLUME ["/root/.turbulence/data"]

ENTRYPOINT ["turbulence"]
CMD ["--help"]
