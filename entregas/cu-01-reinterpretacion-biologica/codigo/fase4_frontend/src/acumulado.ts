// Excel de resultados: lo que se acumula en las hojas Rutas (una fila por ruta) y Genes (sus genes). Sin React, sin
// SheetJS y sin imports, para probarlo con node (pruebas/acumulado.test.ts); ExcelResultados.tsx lo lee y lo escribe.

type Fila = Record<string, unknown>;

export const HOJA_RUTAS = 'Rutas';
export const HOJA_GENES = 'Genes';
export const COLUMNAS_RUTAS = ['Fecha', 'GO_ID', 'Ruta_Nombre', 'Listas', 'Lectura', 'NPS', 'Lectura_automatica', 'NPS_automatico',
  'Cambios_experto', 'NPS_log2FC', 'Lectura_log2FC',
  'Sensible_al_peso', 'n_total', 'n_activan', 'n_inhiben', 'n_neutros', 'n_no_concluyente', 'n_sin_evidencia',
  'n_pendiente', 'Cobertura', 'Genes_activan', 'Genes_inhiben'];
export const COLUMNAS_GENES = ['GO_ID', 'Ruta_Nombre', 'Gen', 'Direccion', 'Log2FC', 'Signo_par', 'Signo_automatico', 'Estado_par', 'Origen',
  'Contribucion', 'Motivos', 'Votos', 'PMIDs_consultados'];

// Lo que devuelve el puente para una ruta: la fila de la ruta (rutas[0]) y sus pares
export interface ResultadoParaExcel {
  rutas: unknown[];
  pares: unknown[];
}

// Lo que cambia al acumular; el resto del estado (fichero, libro…) pasa tal cual
export interface Filas {
  rutas: Fila[];
  genes: Fila[];
  sinGuardar: boolean;
  version: number;
  ultima?: string;
}

const limpio = (v: unknown) => (v === null || v === undefined || (typeof v === 'number' && Number.isNaN(v)) ? '' : v);
const columnas = (f: Fila, cols: string[]) => Object.fromEntries(cols.map((c) => [c, limpio(f[c])]));

// Añade la ruta; si ya estaba, sustituye su fila y sus genes (no se duplica). Sin cambios a mano, el resultado
// automático es el mismo que el guardado.
export const añadirResultado = <A extends Filas>(acc: A, res: ResultadoParaExcel, fecha: Date = new Date()): A => {
  const ruta = res.rutas[0] as Fila;
  const go = String(ruta.GO_ID);
  const fila = columnas({
    Lectura_automatica: ruta.Lectura, NPS_automatico: ruta.NPS, ...ruta, Fecha: fecha.toLocaleString('es-ES'),
  }, COLUMNAS_RUTAS);
  const genes = (res.pares as Fila[]).filter((p) => p.GO_ID === go)
    .map((p) => columnas({ Signo_automatico: p.Signo_par, ...p }, COLUMNAS_GENES));
  return {
    ...acc,
    rutas: [...acc.rutas.filter((r) => String(r.GO_ID) !== go), fila],
    genes: [...acc.genes.filter((g) => String(g.GO_ID) !== go), ...genes],
    sinGuardar: true,
    version: acc.version + 1,
    ultima: go,
  };
};

const cambio = <A extends Filas>(acc: A, rutas: Fila[], genes: Fila[]): A =>
  ({ ...acc, rutas, genes, sinGuardar: true, version: acc.version + 1, ultima: undefined });

// Quita una ruta con sus genes
export const quitarRuta = <A extends Filas>(acc: A, go: string): A =>
  cambio(acc, acc.rutas.filter((r) => String(r.GO_ID) !== go), acc.genes.filter((g) => String(g.GO_ID) !== go));

// Deja el Excel sin rutas (el resto de hojas del libro no se toca)
export const vaciar = <A extends Filas>(acc: A): A => cambio(acc, [], []);
