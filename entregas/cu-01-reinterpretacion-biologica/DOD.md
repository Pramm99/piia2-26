# DoD · Definition of Done (CU-01)

**Qué es.** La lista que tiene que cumplir una tarea para darla por terminada. Es el filtro de salida: evita el «hecho» a medias, sin comprobar, sin documentar o que nadie ha mirado.

**Cuándo se aplica.** Al pasar una tarea de **REVISION** a **DONE**. Quien hace la tarea la deja en REVISION cuando cree que la cumple. El revisor nombrado en el DoR comprueba la lista y la cierra.

**Quién lo comprueba.** Siempre una persona distinta de quien hizo la tarea, sin excepciones por prioridad ni por prisa.

**Igual para todas.** Toda tarea cumple la parte común. Además cumple la parte de su tipo (la que se fijó en el [DoR](DOR.md)). No hay tareas sin DoD.

## Parte común (todas las tareas)

- [ ] **«Hecho cuando» cumplido.** Todos los criterios propios de la tarea están marcados.
- [ ] **Resultado enlazado.** El commit, el fichero o el documento está enlazado desde el issue.
- [ ] **Revisada por otra persona del equipo.** El revisor deja un comentario en el issue: «Revisado contra el DoD».
- [ ] **Tablero al día.** La tarea está en la columna correcta y la etiqueta `Bloqueada` ya no está. Si hubo bloqueos, su línea de cierre está en el issue ([`TABLERO.md`](TABLERO.md#bloqueos)).
- [ ] **Sin trabajo suelto.** Lo que haya salido durante la tarea y no se haya hecho ya es un issue nuevo en Backlog, enlazado desde este.

## Parte por tipo de tarea (se suma a la común)

### Código
- [ ] Pruebas en verde (`python -m pytest` desde `codigo/`), con un test nuevo si la tarea cambia el comportamiento.
- [ ] El comando de ejecución está documentado, y el README, el spec o el ADR están al día si cambia el comportamiento.
- [ ] Ninguna clave en el commit: solo en `codigo/.env`, que no se versiona.

### Documento
- [ ] Coherente con el código y sin contradicciones con [`ARCHITECTURE.md`](ARCHITECTURE.md), los [ADR](decisions/) y los [specs](specs/).
- [ ] Enlaces y cifras comprobados contra la fuente.

### Decisión
- [ ] Decisión escrita en un spec o un ADR, con la cifra o el dato que la justifica.
- [ ] Alternativas descartadas anotadas, con el motivo.

### Gestión
No añade casillas. El «Hecho cuando» debe incluir la prueba de que se hizo: la respuesta recibida, el acta o la fecha acordada.

## Qué hacer si no se cumple

La tarea vuelve de **REVISION** a **Progress** con un comentario del revisor que diga qué casilla falla. No se cierra con casillas pendientes. Si una casilla no se aplica (por ejemplo, un cambio de código que no altera el comportamiento), se marca con la nota «no aplica» y el motivo.

## Ejemplos

- *#23, entrada `.csv` en la Fase 1 (código).* Hecha cuando lee `.csv`, valida las columnas antes de ir a la red, hay un test que lo cubre y `python -m pytest` está en verde.
- *#30, peso del log2FC en el Net Pathway Score (decisión).* Hecha cuando la decisión está en el spec de scoring con el argumento que la justifica y la alternativa descartada.
- *Pedir un dato a CIMUS (gestión).* Hecha cuando hay respuesta de CIMUS con el dato, o con la fecha en que lo enviará, guardada en el issue.

## Relación con otros documentos

- La entrada de la tarea la define [`DOR.md`](DOR.md).
- El ciclo de columnas, el sistema de bloqueos y la rutina de cada reunión están en [`TABLERO.md`](TABLERO.md).
- Las plantillas de issue traen estas casillas ya escritas, una por tipo de tarea: [`docs/plantillas-issue/`](docs/plantillas-issue/).

*Este documento se cambia solo si lo acuerdan las tres personas del equipo.*
