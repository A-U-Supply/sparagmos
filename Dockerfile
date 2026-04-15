FROM python:3.11-slim AS base

# System dependencies for effects
RUN apt-get update && apt-get install -y --no-install-recommends \
    imagemagick \
    netpbm \
    ffmpeg \
    potrace \
    golang-go \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install primitive (geometric shape reconstruction)
RUN GOPATH=/usr/local go install github.com/fogleman/primitive@latest

# Remove Go toolchain after building primitive (saves ~500MB)
RUN apt-get purge -y golang-go git && apt-get autoremove -y

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
