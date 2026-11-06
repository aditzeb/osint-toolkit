# Numint - zero-Python-setup image. Ships the CLI + web UI on one port.
FROM python:3.12-slim

LABEL org.opencontainers.image.title="Numint" \
      org.opencontainers.image.description="Phone number OSINT & intelligence tool (authorized use only)."

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    NUMINT_LOG_LEVEL=WARNING

WORKDIR /app

# Install first (better layer caching), with web + pdf extras so the UI works
# immediately after build - no separate frontend build step is needed because
# the UI ships as prebuilt static assets in the package.
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install --no-cache-dir ".[all]"

# The web UI static assets are packaged; no npm/node build required.
EXPOSE 8080

# Default: serve the web UI. Override CMD to use the CLI, e.g.:
#   docker run --rm numint numint +14155550123
ENTRYPOINT []
CMD ["numint", "web", "--host", "0.0.0.0", "--port", "8080"]
