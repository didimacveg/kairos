# ADR 0001 — Un solo backend, en Python

**Estado:** aceptado · **Fecha:** Fase 1

## Contexto
La propuesta inicial incluia Node.js **y** FastAPI como backends.

## Decision
El backend es exclusivamente Python (FastAPI). Next.js se limita a la interfaz
y a hacer de proxy del mismo origen hacia el nucleo.

## Motivos
- Whisper, OpenCV, YOLO, InsightFace, embeddings y Ollama viven en Python. Un
  backend Node acabaria llamando a procesos Python por subproceso o por HTTP.
- Dos runtimes significan dos gestores de dependencias, dos suites de tests, dos
  Dockerfiles y serializacion cruzada, mantenidos por una sola persona.

## Consecuencias
- Se pierde el ecosistema de librerias de Node en el servidor. Aceptable.
- Si en el futuro hace falta un servicio de tiempo real en Node, sera un
  servicio aparte con contrato explicito, no un segundo backend general.
