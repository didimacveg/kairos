# Imagen del banco de pruebas. Sin CUDA, sin modelos: solo Python y git.
# Cuanto menos tenga dentro, menos hay que pueda usar un parche malicioso.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --gid 10003 forge && \
    useradd --uid 10003 --gid forge --create-home forge && \
    mkdir -p /var/lib/kairos/forge && chown -R forge:forge /var/lib/kairos

WORKDIR /app
COPY apps/forge/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY apps/forge /app

# git se niega a operar sobre repositorios de otro propietario. El repo se
# monta desde el host, asi que hay que declararlo seguro explicitamente.
RUN git config --system --add safe.directory '*'

USER forge
EXPOSE 8300
CMD ["python", "-m", "uvicorn", "service:app", "--host", "0.0.0.0", "--port", "8300"]
