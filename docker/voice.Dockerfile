# Imagen del servicio de voz. Base con cuDNN porque CTranslate2 (el motor de
# faster-whisper) lo necesita para correr en GPU.
FROM nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/var/lib/kairos/models

RUN apt-get update && apt-get install -y --no-install-recommends \
        python3.10 python3-pip \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 'voice' ya existe como grupo del sistema en Ubuntu: usamos otro nombre.
RUN groupadd --gid 10002 kairos && \
    useradd --uid 10002 --gid kairos --create-home kairos && \
    mkdir -p /var/lib/kairos/models && chown -R kairos:kairos /var/lib/kairos

COPY apps/voice/requirements.txt /app/requirements.txt
RUN pip3 install --no-cache-dir -r /app/requirements.txt

COPY apps/voice /app

USER kairos
EXPOSE 8100
CMD ["python3", "-m", "uvicorn", "service:app", "--host", "0.0.0.0", "--port", "8100"]
