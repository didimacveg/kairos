# ADR 0034 — KAIROS decide que merece tu atencion

**Estado:** aceptado · **Fecha:** Fase 31

## El salto
Hasta ahora todo empezaba con Diego. El informe diario fue el primer paso en
la otra direccion, pero a horario fijo. Esto es distinto: KAIROS mira el
estado del sistema y decide si algo merece interrumpir.

## Tres reglas que gobiernan la vigilancia

**Avisa, no actua.** Puede decir que el puente lleva dos horas caido; no
puede reiniciarlo. Un sistema que se arregla solo es un sistema que un dia
decide que tu sesion de trabajo es el problema.

**Solo lo que cambia a peor.** Que todo funcione no es noticia. Un vigilante
que confirma la normalidad es ruido con formato de aviso.

**No se repite.** Un aviso dado no vuelve hasta pasadas 6 horas, y si la
situacion se resuelve, la clave se olvida — cuando vuelva a ocurrir sera un
aviso nuevo y legitimo. Un vigilante que repite lo mismo cada diez minutos
deja de leerse, y entonces no vigila nada.

## Intervalo largo a proposito
20 minutos, no continuo. La vigilancia util no es la que mira cada segundo:
es la que avisa cuando algo lleva un rato mal. Un agente que se cae y vuelve
en treinta segundos no merece interrumpir a nadie.

## Margen al arrancar
90 segundos antes de la primera revision. Durante el primer minuto medio
sistema esta levantandose todavia, y avisaria de caidas que no existen.

## La animacion de despertar
El unico elemento de la interfaz que responde a algo del mundo fisico —oir tu
voz— y por eso el unico al que se le permite ocupar la pantalla entera.

Dura 1,4 s y no se encadena: si se dice el nombre otra vez mientras suena, se
ignora. Una animacion que se repite sobre si misma deja de leerse como evento
y pasa a leerse como fallo.
