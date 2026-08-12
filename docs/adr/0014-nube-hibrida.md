# ADR 0014 — Nube hibrida: donde se rompe el "todo local" y donde no

**Estado:** aceptado · **Fecha:** Fase 3

## Contexto
Con 8 GB de VRAM el techo de razonamiento es un modelo de 8B. Se noto en uso
real: respuestas vagas, incapacidad de responder preguntas simples sobre el
mundo de hoy, y confusion al mezclar memoria con la pregunta.

## Decision
Se separa lo que puede salir de lo que no.

**Sale de casa (opcional, con interruptor):**
- El prompt del turno en curso, cuando se elige proveedor remoto
- Las consultas de busqueda web

**No sale NUNCA, bajo ninguna configuracion:**
- La memoria semantica y sus embeddings
- El historial de conversaciones
- La auditoria
- El calculo de embeddings, que siempre usa Ollama

Esto ultimo esta forzado en codigo, no por convencion: `AnthropicProvider.embed`
lanza `NotImplementedError` y `FailoverProvider.embed` delega siempre en el
proveedor local. No hay ajuste que lo cambie.

## La regla fundacional sigue en pie
"KAIROS nunca depende de Internet para funcionar. Internet solo anade
capacidades, nunca elimina capacidades."

Se cumple con `FailoverProvider`: si la red o la API fallan, la peticion se
reintenta contra Ollama de forma transparente. Internet mejora la calidad; su
ausencia no quita disponibilidad.

Excepcion consciente: si el remoto falla A MEDIA generacion, ya hay tokens en
pantalla y reintentar produciria texto duplicado. Ahi se propaga el error en
vez de caer a local. Es el mal menor.

## Por defecto sigue siendo local
`KAIROS_ALLOW_EGRESS=false` de fabrica. Tener la clave puesta no basta: sin el
interruptor, el proveedor remoto ni se instancia. Y cuando esta activo, la
cabecera lo indica en violeta. Nada sale sin que se vea.

## Busqueda web
Ningun modelo sabe a que hora es el eclipse de hoy: el conocimiento tiene
fecha de corte y no se actualiza solo. Lo que hace que un asistente parezca al
dia es una herramienta de busqueda, no un modelo mas grande.

Se usa el punto de entrada HTML de DuckDuckGo: sin clave, asi que KAIROS
funciona recien clonado sin registrarse en ningun sitio. El parser esta escrito
para devolver lista vacia si el formato cambia, no para reventar.

La decision de buscar se toma ANTES de generar, con una heuristica barata
sobre la pregunta. Buscar de mas cuesta un segundo; no buscar cuando hacia
falta produce una respuesta inventada.

La consulta exacta y las fuentes van en la traza y en la auditoria: el usuario
debe poder ver que se pregunto ahi fuera en su nombre.

## Reloj
El modelo no sabia que dia era porque nadie se lo habia dicho. Se inyecta fecha
y hora en el prompt de sistema. Era el descuido mas barato de arreglar del
proyecto.
