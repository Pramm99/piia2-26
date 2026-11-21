# DoR · Definition of Ready (CU-01)

**Qué es.** La lista que tiene que cumplir una tarea para poder empezarla. Es el filtro de entrada: evita arrancar trabajo sin responsable, sin la entrada que necesita o sin saber cuándo estará terminada.

**Cuándo se aplica.** Al pasar una tarea de **Backlog** (en el tablero, sin estado: *No Status*) a **TODO**. Cualquier idea puede existir como issue en Backlog sin cumplir el DoR; lo que no puede es empezar a trabajarse.

**Quién lo comprueba.** Quien crea la tarea marca las casillas. Quien la va a hacer las confirma antes de moverla a **Progress**. Si hay duda, se decide en la reunión ([`TABLERO.md`](TABLERO.md)).

**Igual para todas.** La lista es la misma para cualquier tarea: código, documento, decisión, gestión o bug.

## Lista

- [ ] **Objetivo y «Hecho cuando» escritos.** El objetivo cabe en una frase. Los criterios de terminado se pueden comprobar con un sí o un no: un comando, una cifra, un fichero, una respuesta recibida.
- [ ] **Tipo de tarea.** Código, documento, decisión o gestión. El tipo decide qué parte variable del [DoD](DOD.md) se le suma.
- [ ] **Responsable y revisor.** Una persona en *Assignees* del issue, que lleva la tarea. Otra persona distinta, nombrada en el issue, que la revisará contra el DoD.
- [ ] **Fecha límite.** En el campo *Target date* del tablero. Si la tarea va a una entrega, la fecha es anterior a la de la entrega.
- [ ] **Prioridad y tamaño.** Campos *Priority* (`P0`/`P1`/`P2`) y *Size* (`XS`/`S`/`M`/`L`/`XL`) del tablero.
- [ ] **La entrada existe.** Lo que la tarea necesita para arrancar ya está: un fichero, una clave, un dato o una decisión previa.
- [ ] **Dependencias pedidas.** Si la tarea necesita algo de fuera del equipo (CIMUS, el profesor, el cupo de una API), **ya se ha pedido**, con fecha de respuesta. Las dependencias de otras tareas están enlazadas (`#N`).

## Qué hacer si no se cumple

La tarea se queda en **Backlog** y en la reunión se dice qué casilla falta y quién la completa.

Si lo único que falta es algo externo que ya se ha pedido, la tarea puede pasar a TODO con la etiqueta `Bloqueada` y la línea de bloqueo que define [`TABLERO.md`](TABLERO.md#bloqueos). No se mueve a TODO «por si acaso» sin haber pedido lo que falta.

## Por qué la casilla de las dependencias pide que ya estén pedidas

Un bloqueo externo cuesta días. Si se pide al empezar la tarea, la respuesta llega mientras se trabaja en lo demás. Si se pide cuando ya hace falta, la tarea se para. Por eso el DoR no se conforma con anotar la dependencia: exige haberla reclamado.

## Ejemplo

*#31, piloto para los 668 pares sin abstract.* Cumple el DoR cuando:
- tiene responsable, revisor, fecha y prioridad;
- los «Hecho cuando» son medibles: pares que ganan abstract y precisión en una muestra de unos 30 pares leída a mano;
- la entrada existe: la Fase 1 de referencia y el registro de respuestas del LLM;
- se conoce el cupo diario de Gemini para las preguntas nuevas.

## Relación con otros documentos

- El cierre de la tarea lo define [`DOD.md`](DOD.md).
- El ciclo de columnas, el sistema de bloqueos y la rutina de cada reunión están en [`TABLERO.md`](TABLERO.md).
- Las plantillas de issue traen estas casillas ya escritas: [`docs/plantillas-issue/`](docs/plantillas-issue/).

*Este documento se cambia solo si lo acuerdan las tres personas del equipo.*
