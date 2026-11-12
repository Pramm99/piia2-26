# Tablero, bloqueos y revisión (CU-01)

Cómo se mueve una tarea por el tablero, qué se hace cuando se bloquea y cómo se revisa el tablero en cada reunión. Las listas de entrada y salida de cada tarea están en [`DOR.md`](DOR.md) y [`DOD.md`](DOD.md).

**Tablero:** GitHub Project «Pia Project» de `Pramm99` (número 1), con los issues de `Pramm99/piia2-26`.

## Ciclo de una tarea

| Columna (*Status*) | Qué significa | Para entrar |
|---|---|---|
| Backlog (*No Status*) | La tarea está escrita, pero todavía no cumple el DoR. | Ser un issue. |
| TODO | Lista para empezar. | Cumplir el [DoR](DOR.md). |
| Progress | El responsable trabaja en ella. | Que el responsable la empiece. |
| REVISION | El revisor la comprueba contra el DoD. | Que el responsable crea que cumple el DoD. |
| DONE | Terminada y cerrada. | Cumplir el [DoD](DOD.md). |
| BUGS | Un error encontrado y todavía sin tratar. | Ser un issue con cómo reproducirlo. Pasa a TODO con el mismo DoR que el resto. |

Una tarea bloqueada **no cambia de columna**: se queda donde estaba y lleva la etiqueta `Bloqueada`. Así el tablero dice a la vez en qué punto está y que no avanza.

**Backlog completo.** Si alguien dice en una reunión o en el chat «tenemos que hacer X», X se convierte en issue ese mismo día, aunque sea en Backlog y con el DoR a medias.

## Bloqueos

Una tarea está bloqueada cuando no puede avanzar por algo que no depende de quien la hace: una respuesta de CIMUS o del profesor, el cupo de una API, otra tarea sin terminar o una decisión del equipo.

### 1. Antes de que ocurra

- **Se piden las dependencias al entrar en TODO**, no cuando hacen falta. El [DoR](DOR.md) no deja pasar una tarea con una dependencia externa sin pedir.
- **Cada dependencia externa tiene fecha de respuesta.** La fecha se fija con margen: al menos tres días antes de la fecha límite de la tarea.
- **Las señales de alerta se miran en cada reunión**, aunque nadie haya dicho que esté bloqueada:
  - una petición externa sin respuesta en dos días hábiles;
  - una tarea en Progress sin commit ni comentario en tres días;
  - una tarea a menos de tres días de su fecha límite y lejos de cumplir el DoD;
  - un cupo de API a punto de agotarse.

  Una señal no es todavía un bloqueo: se pregunta al responsable y, si no puede avanzar, se marca.

### 2. El día que ocurre

El responsable de la tarea, **el mismo día**:

1. Pone la etiqueta `Bloqueada`.
2. Escribe un comentario con esta línea (copiar y rellenar):

   ```
   🔒 Bloqueo · espera a: ___ · lo desbloquea: ___ · lo persigue: @___ · fecha de desbloqueo: DD/MM · plan B: ___
   ```

   - *Espera a:* qué falta, en concreto.
   - *Lo desbloquea:* la persona o el sitio de quien depende (CIMUS, el profesor, Groq, `#N`).
   - *Lo persigue:* la persona del equipo que se encarga de reclamarlo. Suele ser el responsable de la tarea; en lo que depende de CIMUS o del profesor, el PM.
   - *Fecha de desbloqueo:* el último día en que puede llegar sin poner en riesgo la fecha límite.
   - *Plan B:* qué se hará si no llega a tiempo. Puede ser «recortar el alcance a ___». Si no hay plan B, se escribe «sin plan B» y se trata en la reunión siguiente.
3. Hace la primera reclamación ese mismo día, si el bloqueo es externo.
4. Avisa al equipo en el chat con el enlace al issue.

### 3. Si no se desbloquea

| Cuándo | Qué se hace | Quién |
|---|---|---|
| Fecha de desbloqueo vencida | Segunda reclamación y aviso al equipo en el chat. | Quien lo persigue |
| Siguiente reunión, o dos días hábiles después de la fecha | Se decide **una** de estas salidas y se escribe en el issue: plan B, recortar el alcance, cambiar de responsable o dar **una sola** fecha nueva. | El equipo |
| La tarea es `P0` o pone en riesgo una entrega | No se espera a la reunión: se decide en el chat ese mismo día. | El equipo |

Una tarea no puede llevar dos fechas nuevas seguidas: a la segunda se aplica el plan B o se recorta el alcance.

### 4. Al desbloquearse

Se quita la etiqueta `Bloqueada` y se añade un comentario de cierre:

```
🔓 Desbloqueada DD/MM · cómo: ___ (llegó / plan B / alcance recortado) · días bloqueada: N
```

El comentario no se borra: el issue guarda la historia del bloqueo, y el [DoD](DOD.md) pide que esté cerrada.

### Ejemplos reales

- **Etiquetado del gold set por CIMUS (#17).** Esperaba el etiquetado a mano de CIMUS para validar el benchmark. Plan B: quedarse con el etiquetado a ciegas con doble anotador y árbitro (κ 0,98), con la cautela de que el acierto puede estar algo inflado. El 11/11 el equipo aplicó el plan B y cerró la tarea.
- **Cupo diario de Groq (Fase 2).** gpt-oss se paraba al agotar el cupo de tokens del día. Plan B: Gemini como modelo principal y gpt-oss solo como respaldo, así que la ejecución completa no dependió del cupo de Groq.

## Rutina de 10 minutos en cada reunión

1. **Bloqueos primero.** Se filtra el tablero por la etiqueta `Bloqueada`. De cada bloqueo: ¿tiene la línea completa? ¿ha vencido su fecha de desbloqueo? Si ha vencido, se decide la salida (tabla de arriba).
2. **Señales de alerta.** Se repasan las cuatro señales del punto 1 de [Bloqueos](#1-antes-de-que-ocurra).
3. **Columnas de derecha a izquierda:** REVISION, Progress, TODO. De cada tarea: ¿la columna es su estado real? Si no, se corrige en el momento. Lo que lleve más de dos días en REVISION se asigna a un revisor ya.
4. **Backlog.** Las tareas sin responsable, revisor o fecha se completan o se quedan en Backlog.
5. **Tareas nuevas.** Lo que haya salido en la reunión se crea como issue antes de cerrarla.

El PM anota al final, en un comentario del issue de la siguiente entrega, la fecha de la revisión y los cambios hechos.
