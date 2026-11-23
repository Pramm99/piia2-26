// Excel de resultados (src/acumulado.ts): añadir, actualizar sin duplicar, quitar y vaciar.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { añadirResultado, COLUMNAS_GENES, COLUMNAS_RUTAS, quitarRuta, vaciar, type Filas } from '../src/acumulado.ts';

const fecha = new Date(2026, 10, 23, 12, 0, 0);
const vacio: Filas & { nombre: string } = { nombre: 'resultados.xlsx', rutas: [], genes: [], sinGuardar: false, version: 0 };
const resultado = (go: string, lectura: string, nps: number, genes: string[], extra: Record<string, unknown> = {}) => ({
  rutas: [{ GO_ID: go, Ruta_Nombre: `ruta ${go}`, Lectura: lectura, NPS: nps, Interno: 'no va al Excel', ...extra }],
  pares: [...genes.map((g) => ({ GO_ID: go, Gen: g, Signo_par: '+1', Estado_par: 'resuelto', W_pos: 1 })),
    { GO_ID: 'GO:otra', Gen: 'Z', Signo_par: '-1' }], // de otra ruta: no entra
});

test('añadir dos rutas: una fila por ruta y sus genes, con las columnas del Excel', () => {
  let acc = añadirResultado(vacio, resultado('GO:1', 'activada', 0.5, ['A', 'B']), fecha);
  acc = añadirResultado(acc, resultado('GO:2', 'mixta', 0, ['C']), fecha);
  assert.equal(acc.nombre, 'resultados.xlsx'); // el resto del estado pasa tal cual
  assert.deepEqual(acc.rutas.map((r) => r.GO_ID), ['GO:1', 'GO:2']);
  assert.deepEqual(acc.genes.map((g) => g.Gen), ['A', 'B', 'C']);
  assert.deepEqual(Object.keys(acc.rutas[0]), COLUMNAS_RUTAS); // ni más ni menos columnas
  assert.deepEqual(Object.keys(acc.genes[0]), COLUMNAS_GENES);
  assert.equal(acc.rutas[0].Fecha, fecha.toLocaleString('es-ES'));
  // Sin cambios a mano, el resultado automático es el mismo; lo que falta va vacío
  assert.deepEqual([acc.rutas[0].Lectura_automatica, acc.rutas[0].NPS_automatico, acc.rutas[0].Cambios_experto], ['activada', 0.5, '']);
  assert.equal(acc.genes[0].Signo_automatico, '+1');
  assert.deepEqual([acc.sinGuardar, acc.version, acc.ultima], [true, 2, 'GO:2']);
});

test('repetir una ruta la actualiza sin duplicarla', () => {
  let acc = añadirResultado(vacio, resultado('GO:1', 'activada', 0.5, ['A', 'B']), fecha);
  acc = añadirResultado(acc, resultado('GO:2', 'mixta', 0, ['C']), fecha);
  acc = añadirResultado(acc, resultado('GO:1', 'mixta', 0.25, ['A'], {
    Lectura_automatica: 'activada', NPS_automatico: 0.5, Cambios_experto: 'B: +1 → neutro',
  }), fecha);
  assert.deepEqual(acc.rutas.map((r) => [r.GO_ID, r.Lectura, r.Lectura_automatica, r.Cambios_experto]),
    [['GO:2', 'mixta', 'mixta', ''], ['GO:1', 'mixta', 'activada', 'B: +1 → neutro']]);
  assert.deepEqual(acc.genes.map((g) => `${g.GO_ID}:${g.Gen}`), ['GO:2:C', 'GO:1:A']);
});

test('quitar una ruta y vaciar el Excel', () => {
  let acc = añadirResultado(vacio, resultado('GO:1', 'activada', 0.5, ['A']), fecha);
  acc = añadirResultado(acc, resultado('GO:2', 'mixta', 0, ['C']), fecha);
  const sin1 = quitarRuta(acc, 'GO:1');
  assert.deepEqual([sin1.rutas.map((r) => r.GO_ID), sin1.genes.map((g) => g.Gen)], [['GO:2'], ['C']]);
  assert.deepEqual([sin1.sinGuardar, sin1.version, sin1.ultima], [true, 3, undefined]);
  const limpio = vaciar(sin1);
  assert.deepEqual([limpio.rutas, limpio.genes, limpio.nombre], [[], [], 'resultados.xlsx']);
});
