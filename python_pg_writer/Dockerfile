FROM python:3.11-slim

WORKDIR /app

# Copy the project structure (build context should be the datapipeline root)
COPY python_pg_ui/ ./python_pg_ui/
COPY python_pg_writer/ ./python_pg_writer/

WORKDIR /app/python_pg_writer

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health')" || exit 1

# Run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
