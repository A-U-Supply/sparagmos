# Stage 1: Build primitive from Go source
FROM golang:1.22-bookworm AS go-builder
RUN go install github.com/fogleman/primitive@latest

# Stage 2: Main image
FROM python:3.11-slim

# System dependencies for effects
RUN apt-get update && apt-get install -y --no-install-recommends \
    imagemagick \
    netpbm \
    ffmpeg \
    potrace \
    && rm -rf /var/lib/apt/lists/*

# Copy primitive binary from Go build stage
COPY --from=go-builder /go/bin/primitive /usr/local/bin/primitive

# Relax ImageMagick policy (default Debian policy blocks many operations)
RUN if [ -f /etc/ImageMagick-6/policy.xml ]; then \
      sed -i 's/rights="none"/rights="read|write"/g' /etc/ImageMagick-6/policy.xml; \
    fi

WORKDIR /app

RUN pip install uv
COPY pyproject.toml .
COPY sparagmos/ sparagmos/
COPY recipes/ recipes/
RUN uv pip install --system .

WORKDIR /work

ENTRYPOINT ["python", "-m", "sparagmos"]
