FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install Python deps as root so site-packages is writable here only.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code (HTML/JS/static included via samples/ and static/).
COPY app/ ./app/
COPY samples/ ./samples/
COPY static/ ./static/

# Run as a non-root user. /app contents are world-readable; downloads go to /tmp.
RUN useradd --create-home --shell /bin/bash --uid 1000 app \
 && chown -R app:app /app
USER app

EXPOSE 8080

# Liveness probe: hit /api/samples (returns the sample list — fast, no SignNow API).
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request,sys; \
                  urllib.request.urlopen('http://localhost:8080/api/samples', timeout=2)" \
      || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
