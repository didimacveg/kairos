# El unico servicio que escribe en el repositorio. Minimo: Python y git.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY apps/warden/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY apps/warden /app

RUN git config --system --add safe.directory '*' && \
    git config --system user.email "kairos@local" && \
    git config --system user.name "KAIROS Smith"

EXPOSE 8400
CMD ["python", "-m", "uvicorn", "service:app", "--host", "0.0.0.0", "--port", "8400"]
