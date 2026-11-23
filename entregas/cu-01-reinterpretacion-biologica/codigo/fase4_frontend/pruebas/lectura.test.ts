// «Tu criterio» en pantalla (src/lectura.ts). La comparación con fase3_scoring/nps.py está en
// codigo/tests/test_interfaz.py, que también lanza estas pruebas.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { aplicarCriterio, genesParaCambiar, recalcularRuta, redondear, type ParRuta } from '../src/lectura.ts';

const par = (Gen: string, Signo_par: string, Direccion = 'up', Estado_par = 'resuelto', Log2FC: number | null = null): ParRuta => ({
  Gen, Direccion, Signo_par, Estado_par, Origen: 'LLM', Motivos: '', Log2FC,
  Contribucion: Estado_par !== 'resuelto' || Signo_par === 'neutro' || Signo_par === 'UNKNOWN' ? 0
    : (Signo_par === '+1' ? 1 : -1) * (Direccion === 'up' ? 1 : -1),
});
const ruta = { NPS: null, Lectura: '', n_activan: 0, n_inhiben: 0, n_pendiente: 0, Cobertura: 0 };

test('aplicarCriterio: el signo del experto, con la dirección del gen', () => {
  const [a, b, c] = aplicarCriterio([par('A', 'UNKNOWN', 'up', 'no_concluyente'), par('B', '+1', 'down'), par('C', '+1')],
    { A: '+1', B: '+1' });
  assert.deepEqual([a.Signo_par, a.Estado_par, a.Origen, a.Motivos, a.Contribucion], ['+1', 'resuelto', 'Experto', 'criterio_experto', 1]);
  assert.equal(b.Contribucion, -1); // gen down que activa: frena la ruta
  assert.equal(c.Origen, 'LLM'); // sin cambio, tal cual
  assert.equal(aplicarCriterio([par('A', '+1')], { A: 'neutro' })[0].Contribucion, 0);
});

test('recalcularRuta: NPS, lectura y recuentos', () => {
  const pares = [par('A', '+1'), par('B', '+1'), par('C', '-1'), par('D', 'neutro'), par('E', 'UNKNOWN', 'up', 'no_concluyente')];
  const r = recalcularRuta(ruta, pares);
  assert.equal(r.NPS, 0.333); // (1 + 1 − 1) / 3
  assert.equal(r.Lectura, 'activada');
  assert.equal(r.Cobertura, 0.8);
  assert.deepEqual([r.n_activan, r.n_inhiben, r.n_pendiente], [2, 1, 0]);
  assert.equal(recalcularRuta(ruta, pares.slice(0, 2)).Lectura, 'insuficiente'); // menos de 3 con signo
  assert.equal(recalcularRuta(ruta, [par('A', '+1'), par('B', '-1'), par('C', '+1'), par('D', '-1')]).Lectura, 'mixta');
});

test('recalcularRuta: poca cobertura da insuficiente', () => {
  const sinSigno = Array.from({ length: 8 }, (_, i) => par(`X${i}`, 'UNKNOWN', 'up', 'no_concluyente'));
  const r = recalcularRuta(ruta, [par('A', '-1'), par('B', '-1'), par('C', '-1'), ...sinSigno]);
  assert.equal(r.NPS, -1);
  assert.equal(r.Lectura, 'insuficiente'); // 3 de 11 = 27 % < 30 %
});

test('recalcularRuta: con log2FC, el NPS pesado y si la lectura es sensible al peso', () => {
  const pares = [par('A', '+1', 'up', 'resuelto', 4), par('B', '+1', 'up', 'resuelto', 0.5), par('C', '-1', 'up', 'resuelto', 3)];
  const r = recalcularRuta({ ...ruta, Lectura_log2FC: 'mixta' }, pares);
  assert.equal(r.NPS, 0.333);
  assert.equal(r.NPS_log2FC, 0.2); // (4 + 0,5 − 3) / 7,5
  assert.deepEqual([r.Lectura, r.Lectura_log2FC, r.Sensible_al_peso], ['activada', 'mixta', 'sí']);
  assert.equal(recalcularRuta(ruta, pares).Sensible_al_peso, ''); // sin tabla de log2FC
});

test('genesParaCambiar: cuántos genes a favor sostienen la lectura', () => {
  assert.equal(genesParaCambiar(6, 3), 1); // 6 a favor y 3 en contra: con uno menos, (5 − 3) / 8 < 0,33
  assert.equal(genesParaCambiar(5, 0), 3); // con 2 menos quedan 3 (100 %); con 3 menos, menos de 3 con signo
});

test('redondear: como round(v, 3) de Python, también en los empates', () => {
  assert.deepEqual([0.5625, -0.5625, 0.0625, 0.1875, 0.3125, 1 / 3, -2 / 3, 0.0125, 0.333, 1].map(redondear),
    [0.562, -0.562, 0.062, 0.188, 0.312, 0.333, -0.667, 0.013, 0.333, 1]);
  assert.equal(redondear(null), null);
});
