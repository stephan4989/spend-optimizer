FROM python:3.11-slim

WORKDIR /app

# System deps for JAX / numpy
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Google Meridian: Linux-only (requires TensorFlow 2.19+ which has no macOS wheel)
RUN pip install --no-cache-dir git+https://github.com/google/meridian.git

COPY . .

ENV PYTHONPATH=/app
