FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install Python dependencies first so Docker can cache this layer.
COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application source.
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini
COPY README.md ./README.md

# Create writable runtime directories.
RUN mkdir -p uploads/avatars logs

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]