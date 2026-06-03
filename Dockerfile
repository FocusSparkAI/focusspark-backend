FROM python:3.12.3-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# cd is same like WORKDIR
WORKDIR /app

# Install Linux libraries needed by OpenCV / MediaPipe
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libgl1 \
        libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# COPY source dest . or / same
COPY requirements.txt .

# Want to execute an instruction during build time
RUN python -m pip install --upgrade pip \
    && pip install -r requirements.txt

# Copy this project backend app into the image
COPY app ./app

# Create runtime folder for logs
RUN mkdir -p logs

EXPOSE 8000

# Start FastAPI backend server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
