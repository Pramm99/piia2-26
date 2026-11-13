# Plantilla de tarea (CU-01)

Texto para pegar en el cuerpo de un issue de `Pramm99/piia2-26`. Los formularios `tarea-*.yml` de esta carpeta tienen el mismo contenido, pero GitHub solo los lee desde `.github/ISSUE_TEMPLATE/` en la raíz del repositorio, que es de la asignatura. Definiciones: [`DOR.md`](../../DOR.md), [`DOD.md`](../../DOD.md) y [`TABLERO.md`](../../TABLERO.md).

Se pega todo el bloque. De la parte por tipo del DoD se deja solo la del tipo de la tarea.

```markdown
<!-- dor-dod -->
**Tipo:** código / documento / decisión / gestión
**Responsable:** @usuario · **Revisor:** @usuario
**Fecha límite:** DD/MM (campo Target date del tablero)

## Objetivo
Una frase: qué se quiere conseguir y para qué.

## Hecho cuando
- [ ] ...

## DoR: lista para empezar
- [ ] Objetivo y «Hecho cuando» escritos arriba, con criterios que se comprueban con un sí o un no
- [ ] Tipo de tarea elegido (esta plantilla)
- [ ] Responsable en Assignees y revisor (otra persona) nombrado arriba
- [ ] Fecha límite en el campo Target date del tablero
- [ ] Prioridad (P0/P1/P2) y tamaño (XS/S/M/L/XL) en los campos del tablero
- [ ] La entrada necesaria existe (fichero, clave, dato o decisión previa)
- [ ] Dependencias externas ya pedidas, con fecha de respuesta; dependencias internas enlazadas (#N)

## DoD: terminada
- [ ] Todos los criterios del «Hecho cuando» cumplidos
- [ ] Resultado enlazado (commit, fichero o documento)
- [ ] Revisada por otra persona del equipo (comentario «Revisado contra el DoD»)
- [ ] Tablero al día: columna correcta, sin la etiqueta Bloqueada y con los bloqueos cerrados en el issue
- [ ] Lo que salió y no se hizo ya es un issue nuevo enlazado
<!-- Código -->
- [ ] Pruebas en verde (python -m pytest desde codigo/), con un test nuevo si cambia el comportamiento
- [ ] Comando de ejecución documentado; README, spec o ADR al día si cambia el comportamiento
- [ ] Ninguna clave en el commit (solo en codigo/.env)
<!-- Documento -->
- [ ] Coherente con el código y sin contradicciones con ARCHITECTURE.md, los ADR y los specs
- [ ] Enlaces y cifras comprobados contra la fuente
<!-- Decisión -->
- [ ] Decisión escrita en un spec o un ADR, con la cifra o el dato que la justifica
- [ ] Alternativas descartadas anotadas, con el motivo
<!-- Gestión: sin casillas añadidas; el «Hecho cuando» incluye la prueba (respuesta, acta o fecha) -->

## Bloqueos y dependencias
Ninguno.
<!-- Si se bloquea: etiqueta Bloqueada y un comentario con
🔒 Bloqueo · espera a: ___ · lo desbloquea: ___ · lo persigue: @___ · fecha de desbloqueo: DD/MM · plan B: ___ -->
```
