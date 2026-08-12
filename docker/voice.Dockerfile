# Imagen del servicio de voz: Whisper (transcripcion) y Piper (sintesis).
# Base con cuDNN por si algun dia se devuelve Whisper a GPU; hoy ambos motores
# corren en CPU para dejar la VRAM entera al modelo de razonamiento.
FROM nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/var/lib/kairos/models \
    KAIROS_PIPER_DIR=/var/lib/kairos/voices

RUN apt-get update && apt-get install -y --no-install-recommends \
        python3.10 python3-pip curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN groupadd --gid 10002 kairos && \
    useradd --uid 10002 --gid kairos --create-home kairos && \
    mkdir -p /var/lib/kairos/models /var/lib/kairos/voices

# Voz espanola de Piper. Se descarga en build para que el contenedor arranque
# sin red: KAIROS debe hablar con el router desenchufado.
ARG PIPER_VOICE=es_ES-davefx-medium
ARG PIPER_BASE=https://huggingface.co/rhasspy/piper-voices/resolve/main/es/es_ES/davefx/medium
RUN curl -fsSL "${PIPER_BASE}/${PIPER_VOICE}.onnx" \
        -o "/var/lib/kairos/voices/${PIPER_VOICE}.onnx" && \
    curl -fsSL "${PIPER_BASE}/${PIPER_VOICE}.onnx.json" \
        -o "/var/lib/kairos/voices/${PIPER_VOICE}.onnx.json"

RUN chown -R kairos:kairos /var/lib/kairos

COPY apps/voice/requirements.txt /app/requirements.txt
RUN pip3 install --no-cache-dir -r /app/requirements.txt

COPY apps/voice /app

USER kairos
EXPOSE 8100
CMD ["python3", "-m", "uvicorn", "service:app", "--host", "0.0.0.0", "--port", "8100"]
