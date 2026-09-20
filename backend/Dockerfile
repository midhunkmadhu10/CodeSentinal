FROM python:3.11-slim

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

RUN addgroup --system app && adduser --system --ingroup app app \
    && chown -R app:app /app
USER app

# Expose backend port
EXPOSE 8000

# Unauthenticated liveness probe — fails the container if the app stops serving
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; \
        urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4) \
        or sys.exit(1)"

# Run the FastAPI application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
