// El estudio en la interfaz (src/estudio.ts, #51): etiqueta, qué tipos celulares pesan la mitad y lectura de /estudio.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { celulaPenaliza, celulasQuePesanEntero, ESTUDIO_NK, etiquetaEstudio, leerEstudio } from '../src/estudio.ts';

const T = { celula: 'células T', cl_celula: 'CL:0000084', clase_celula: 'inmune', tejido: 'pulmón',
  tipos_celulares_validos: ['NK', 'T', 'other_immune', 'not_stated'] };
const EPITELIO = { celula: 'células epiteliales', cl_celula: 'CL:0000066', clase_celula: 'otra', tejido: 'colon',
  tipos_celulares_validos: ['other', 'not_stated'] };

test('etiqueta de la cabecera con la célula y el tejido del estudio', () => {
  assert.equal(etiquetaEstudio(ESTUDIO_NK), 'Células NK · Laringe y faringe (HNSC)');
  assert.equal(etiquetaEstudio(leerEstudio(T)), 'Células T · Pulmón');
});

test('pesa la mitad un artículo en un tipo celular de otra clase; sin dato, no', () => {
  assert.deepEqual(['NK', 'T', 'tumor', 'other', ''].map((t) => celulaPenaliza(ESTUDIO_NK, t)), [false, false, true, true, false]);
  const e = leerEstudio(EPITELIO);
  assert.deepEqual(['NK', 'tumor', 'other', 'not_stated'].map((t) => celulaPenaliza(e, t)), [true, true, false, false]);
  assert.equal(celulasQuePesanEntero(e), 'células no inmunes ni tumorales');
});

test('una respuesta incompleta o de un puente sin /estudio deja el estudio de CIMUS', () => {
  assert.deepEqual(leerEstudio(null), ESTUDIO_NK);
  assert.deepEqual(leerEstudio({ celula: 'x', tejido: 'y', clase_celula: 'rara', tipos_celulares_validos: [] }), ESTUDIO_NK);
  assert.equal(leerEstudio(T).celula, 'células T');
});
