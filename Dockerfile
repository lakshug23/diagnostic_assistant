# Use Python 3.11 slim image as base
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV FLASK_ENV=production

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        gcc \
        g++ \
        libc6-dev \
        libmagic1 \
        libffi-dev \
        libssl-dev \
        build-essential \
        curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN groupadd -r medsage && useradd -r -g medsage medsage

# Copy requirements and install Python dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY backend/ ./backend/
COPY malaria_detect_model.keras ./
COPY uploads/ ./uploads/

# Set Python path to include current directory
ENV PYTHONPATH=/app:$PYTHONPATH

# Create necessary directories
RUN mkdir -p logs uploads \
    && chown -R medsage:medsage /app

# Switch to non-root user
USER medsage

# Expose port
EXPOSE 5001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:5001/health || exit 1

# Command to run the application
CMD ["gunicorn", "--bind", "0.0.0.0:5001", "--workers", "4", "--timeout", "120", "--keep-alive", "5", "--access-logfile", "-", "--error-logfile", "-", "backend.app_enhanced:app"]
