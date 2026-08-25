# ADR 0045 — Una capa, varios proveedores de voz

**Estado:** aceptado · **Fecha:** Fase 44

## Por que una capa
En tres fases hemos cambiado de Piper a Deepgram y de Deepgram a otra cosa, y
cada cambio fue un parche al servicio entero.

Con esta capa, cambiar de proveedor es una linea del .env.

## El orden
    elevenlabs -> deepgram -> piper

Y **siempre termina en piper**. Si los remotos fallan, KAIROS habla igual:
peor, pero habla. Regla de la Fase 1, intacta.

## Por que ElevenLabs para esto
Ninguna voz de catalogo suena a JARVIS, y no es casualidad: los catalogos se
disenan para atencion al cliente, donde una voz calida vende y una voz
metalica asusta. Todas las voces masculinas en espanol de cualquier proveedor
tienen ese sesgo.

ElevenLabs es el unico con **Voice Design**: describes la voz en texto y la
genera. Es la unica via para tener una voz que no existe en ningun catalogo.

## Los parametros que importan
- `stability` alto (0.55-0.7): mas monotono y predecible entre frases. En una
  voz de sistema eso es una virtud; en un audiolibro seria un defecto.
- `style` moderado (0.3-0.4): exagera el caracter de la voz. En una voz grave
  la hace mas grave. Por encima de 0.6 empieza a sonar forzada.
- `eleven_flash_v2_5`: ~75 ms y mitad de coste. `multilingual_v2` suena algo
  mejor pero tarda mas; para conversar no compensa.

## Endpoint /voces
Lista las voces de la cuenta para elegir sin salir de KAIROS: pruebas una,
pegas su id en el .env, recreas el contenedor.
