FROM mcr.microsoft.com/devcontainers/python:1-3.11-bullseye

# System dependencies for OCR, image processing, playwright
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-kor \
    tesseract-ocr-chi-sim \
    libgl1-mesa-glx \
    libglib2.0-0 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies - all subprojects
COPY pm-agent/requirements.txt /tmp/pm-agent-req.txt
COPY daily-scout/requirements.txt /tmp/daily-scout-req.txt
COPY image-localization-system/backend/requirements.txt /tmp/image-loc-req.txt

RUN pip install --no-cache-dir \
    -r /tmp/pm-agent-req.txt \
    -r /tmp/daily-scout-req.txt \
    -r /tmp/image-loc-req.txt \
    && rm /tmp/*-req.txt

# Playwright browser (for Daily Scout crawling)
RUN playwright install chromium && playwright install-deps chromium
