"""Los prompts de KAIROS, en un sitio.

POR QUE ESTE PAQUETE: los prompts vivian dentro de cada agente, y cada fase
anadia reglas al que tocaba. El resultado eran ocho voces distintas: el
informe hablaba de una forma, el razonamiento de otra, la curiosidad de otra.

Peor: reglas que deberian valer para todos —no usar muletillas, no inventar,
decir cuando no se sabe— estaban en unos y en otros no, segun cuando se
escribieron.

Aqui viven la IDENTIDAD comun y las reglas que gobiernan a todos. Cada agente
sigue teniendo su prompt propio para lo suyo, pero parte de la misma base.
"""
from kairos.prompts.base import (
    IDENTIDAD,
    REGLAS_ESCRITO,
    REGLAS_HABLADO,
    componer,
    honestidad,
)

__all__ = [
    "IDENTIDAD",
    "REGLAS_ESCRITO",
    "REGLAS_HABLADO",
    "componer",
    "honestidad",
]
