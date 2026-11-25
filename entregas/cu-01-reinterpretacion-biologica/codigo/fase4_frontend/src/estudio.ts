// El estudio que se analiza (codigo/estudio.json, #51): la interfaz lo pide al puente (GET /estudio) para nombrar
// la célula y el tejido y para explicar el peso de cada artículo como lo calcula fase3_scoring/nps.py:peso.
import { createContext } from 'react';
import type { Fila } from './comun';

// Versión 2 (#52): elegir la célula y subir una tabla de log2FC para cada ejecución. El puente ya lo admite
// (POST /ejecutar-ruta con Celula y Log2FC), pero en esta versión los controles se ven congelados. Para activarlos
// basta con poner true aquí y volver a compilar la interfaz.
export const VERSION_2 = false;

export interface CelulaDisponible {
  cl_celula: string;
  celula: string;
  clase_celula: 'inmune' | 'tumoral' | 'otra';
}

export interface Estudio {
  celula: string; // «células NK»
  cl_celula: string;
  clase_celula: 'inmune' | 'tumoral' | 'otra';
  tejido: string;
  tipos_celulares_validos: string[]; // tipos celulares del LLM que pesan entero
  celulas_disponibles?: CelulaDisponible[]; // las que se pueden elegir (versión 2)
}

// Mientras el puente no responde (o es una versión anterior sin /estudio): el estudio de CIMUS
export const ESTUDIO_NK: Estudio = {
  celula: 'células NK', cl_celula: 'CL:0000623', clase_celula: 'inmune', tejido: 'laringe y faringe (HNSC)',
  tipos_celulares_validos: ['NK', 'T', 'other_immune', 'not_stated'],
};

export const EstudioContexto = createContext<Estudio>(ESTUDIO_NK);

const mayuscula = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

// Etiqueta de la cabecera: «Células NK · Laringe y faringe (HNSC)»
export const etiquetaEstudio = (e: Estudio) => `${mayuscula(e.celula)} · ${mayuscula(e.tejido)}`;

// Lo que el LLM puede decir del tipo celular de un artículo (fase2_inferencia/esquema.py), en palabras
export const TIPO_CELULAR_TEXTO: Record<string, string> = {
  NK: 'células NK', T: 'células T', other_immune: 'otras células inmunes', tumor: 'células tumorales',
  other: 'células no inmunes',
};

// Qué tipos celulares pesan entero, en palabras, para la explicación del peso
export const celulasQuePesanEntero = (e: Estudio) =>
  ({ inmune: 'células inmunes', tumoral: 'células tumorales', otra: 'células no inmunes ni tumorales' })[e.clase_celula];

// ¿Pesa la mitad un artículo por su tipo celular? Sin dato del modelo, no.
export const celulaPenaliza = (e: Estudio, tipo: string) => tipo !== '' && !e.tipos_celulares_validos.includes(tipo);

// Lee la respuesta de GET /estudio; si falta algo, el estudio de CIMUS
export const leerEstudio = (datos: unknown): Estudio => {
  const d = (datos || {}) as Partial<Estudio>;
  const clases = ['inmune', 'tumoral', 'otra'];
  if (!d.celula || !d.tejido || !d.clase_celula || !clases.includes(d.clase_celula) || !Array.isArray(d.tipos_celulares_validos)) {
    return ESTUDIO_NK;
  }
  const celulas = Array.isArray(d.celulas_disponibles)
    ? d.celulas_disponibles.filter((c) => c && c.cl_celula && c.celula && clases.includes(c.clase_celula))
    : [];
  return { celula: d.celula, cl_celula: d.cl_celula || '', clase_celula: d.clase_celula, tejido: d.tejido,
    tipos_celulares_validos: d.tipos_celulares_validos, celulas_disponibles: celulas };
};

// Tabla de log2FC subida en la interfaz (versión 2): la misma que acepta la Fase 3 (fase3_scoring/nps.py:leer_log2fc).
// Columnas Gen y log2FC, o la tabla de DESeq2 tal cual: el gen en la primera columna, sin nombre (SheetJS la llama
// __EMPTY), y log2FoldChange. Devuelve {GEN: valor}; se saltan las filas sin gen o sin número.
export const leerTablaLog2fc = (filas: Fila[]): Record<string, number> => {
  if (!filas.length) throw new Error('La tabla de log2FC está vacía.');
  const columnas = Object.keys(filas[0]);
  const colGen = ['Gen', 'gene', 'Gene', '__EMPTY'].find((c) => columnas.includes(c)) ?? columnas[0];
  const colFC = ['log2FC', 'log2FoldChange'].find((c) => columnas.includes(c));
  if (!colFC) throw new Error('La tabla de log2FC necesita una columna log2FC o log2FoldChange.');
  const valores: Record<string, number> = {};
  for (const f of filas) {
    const gen = String(f[colGen] ?? '').trim().toUpperCase();
    const v = typeof f[colFC] === 'number' ? (f[colFC] as number) : Number(String(f[colFC] ?? '').replace(',', '.'));
    if (gen && String(f[colFC] ?? '').trim() !== '' && Number.isFinite(v)) valores[gen] = v;
  }
  if (!Object.keys(valores).length) throw new Error('La tabla de log2FC no tiene ningún gen con un valor numérico.');
  return valores;
};

// Lo que se añade a POST /ejecutar-ruta: nada mientras la versión 2 esté congelada
export const extrasVersion2 = (activa: boolean, celula: string, log2fc: Record<string, number> | null) =>
  activa ? { ...(celula ? { Celula: celula } : {}), ...(log2fc ? { Log2FC: log2fc } : {}) } : {};
