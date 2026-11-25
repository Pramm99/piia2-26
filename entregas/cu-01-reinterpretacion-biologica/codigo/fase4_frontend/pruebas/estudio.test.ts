// El estudio en la interfaz (src/estudio.ts, #51): etiqueta, qué tipos celulares pesan la mitad y lectura de /estudio.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { celulaPenaliza, celulasQuePesanEntero, ESTUDIO_NK, etiquetaEstudio, extrasVersion2, leerEstudio, leerTablaLog2fc,
  VERSION_2 } from '../src/estudio.ts';

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

test('versión 2: las células que se pueden elegir, sin las mal formadas', () => {
  const e = leerEstudio({ ...T, celulas_disponibles: [
    { cl_celula: 'CL:0000623', celula: 'células NK', clase_celula: 'inmune' },
    { cl_celula: 'CL:0001064', celula: 'células tumorales', clase_celula: 'tumoral' },
    { cl_celula: 'CL:1', celula: 'rara', clase_celula: 'otra cosa' }] });
  assert.deepEqual(e.celulas_disponibles?.map((c) => c.cl_celula), ['CL:0000623', 'CL:0001064']);
});

test('versión 2: tabla de log2FC con Gen y log2FC, o la de DESeq2 tal cual', () => {
  assert.deepEqual(leerTablaLog2fc([{ Gen: 'cd7', log2FC: 2.5 }, { Gen: 'GZMB', log2FC: '-1,5' }, { Gen: '', log2FC: 1 }]),
    { CD7: 2.5, GZMB: -1.5 });
  assert.deepEqual(leerTablaLog2fc([{ __EMPTY: 'PRF1', baseMean: 10, log2FoldChange: 3.1 }, { __EMPTY: 'KLRD1', log2FoldChange: 'NA' }]),
    { PRF1: 3.1 });
  assert.throws(() => leerTablaLog2fc([{ Gen: 'CD7', padj: 0.01 }]), /log2FC o log2FoldChange/);
  assert.throws(() => leerTablaLog2fc([]), /vacía/);
});

test('versión 2 congelada: la ejecución no lleva ni célula ni log2FC', () => {
  assert.equal(VERSION_2, false);
  assert.deepEqual(extrasVersion2(VERSION_2, 'CL:0001064', { CD7: 1 }), {});
  assert.deepEqual(extrasVersion2(true, 'CL:0001064', { CD7: 1 }), { Celula: 'CL:0001064', Log2FC: { CD7: 1 } });
  assert.deepEqual(extrasVersion2(true, '', null), {});
});
