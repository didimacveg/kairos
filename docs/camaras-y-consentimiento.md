# Camaras y consentimiento — requisito bloqueante de la Fase 3

Alcance declarado: las camaras cubriran **zonas comunes de la vivienda, con
familia presente**. Esto cambia la naturaleza legal del proyecto y hay que
resolverlo antes de escribir una linea del Vision Agent, no despues.

## Por que no es un detalle

Los datos biometricos (un embedding facial lo es) son **categoria especial** en
el articulo 9 del RGPD. La excepcion domestica del articulo 2.2.c cubre la
actividad personal en el ambito privado, pero es estrecha: decae en cuanto se
capta a personas fuera del nucleo, se enfoca espacio comun de un edificio o via
publica, o los datos salen del ambito domestico. La AEPD ha sancionado
instalaciones domesticas por enfocar zonas ajenas.

Ademas: el sistema se instala en una vivienda que no es tuya. La autorizacion de
quien la habita no es una formalidad, es el permiso para que el proyecto exista.

## Requisitos de diseno que se derivan (no negociables)

1. **Consentimiento previo, informado y por persona.** Nadie entra en el sistema
   de reconocimiento sin haber dicho que si, sabiendo que se guarda y para que.
   Se registra en una tabla `consents` con fecha y alcance. Se puede retirar, y
   retirarlo borra los datos ese mismo dia.
2. **Cero imagenes crudas persistidas.** El pipeline guarda embeddings y
   metadatos. Los frames viven en memoria y se descartan. Si necesitas depurar,
   usa un modo de desarrollo explicito con borrado automatico.
3. **Embeddings cifrados en reposo** con clave separada de la de la base de datos.
4. **Ninguna camara en espacios de intimidad.** Banos y dormitorios ajenos quedan
   fuera por diseno, no por configuracion.
5. **Ninguna camara enfocando via publica, rellano, patio comun ni vivienda
   vecina.** Si el encuadre lo incluye, se recorta por software antes de
   procesar y se documenta el encuadre.
6. **Indicador fisico de actividad.** Un LED visible cuando la camara procesa.
   Que la gente sepa cuando esta siendo analizada sin tener que preguntar.
7. **Interruptor fisico de corte.** Accesible por cualquiera de la casa, no solo
   por ti.
8. **Nada de reconocimiento facial como autenticacion.** Identifica quien esta
   en la sala; no concede permisos. Una foto en un movil derrota un embedding.

## Puerta de entrada a la Fase 3

La Fase 3 no empieza hasta que exista:

- `docs/consentimientos/` con un documento firmado (en papel vale) por cada
  persona de la casa, y autorizacion expresa de quien es responsable de la
  vivienda;
- un diagrama del encuadre de cada camara;
- el procedimiento de borrado probado de extremo a extremo.

Si alguien de la casa dice que no, esa persona no se registra y el sistema debe
funcionar igual sin ella. Un sistema que necesita que todos digan que si esta
mal disenado.
