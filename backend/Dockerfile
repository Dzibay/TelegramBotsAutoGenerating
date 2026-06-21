FROM python:3.11-slim

WORKDIR /app

# opentele → PyQt5 needs glib (libgthread-2.0.so.0) and basic X11 libs in slim images
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    libglib2.0-0 \
    libgl1 \
    libdbus-1-3 \
    libxkbcommon0 \
    libxcb1 \
    libx11-6 \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .
COPY database/ /app/database/

RUN sed -i 's/\r$//' /app/docker-entrypoint.sh && chmod +x /app/docker-entrypoint.sh

EXPOSE 5000

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["gunicorn", "app.main:app", "-k", "uvicorn.workers.UvicornWorker", "-b", "0.0.0.0:5000", "--workers", "2", "--timeout", "300", "--graceful-timeout", "30"]
