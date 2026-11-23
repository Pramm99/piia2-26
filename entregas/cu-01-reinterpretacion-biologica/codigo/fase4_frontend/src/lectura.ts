// Lectura de una ruta con los cambios de «Tu criterio», recalculada en pantalla al momento. Es la misma cuenta que
// fase3_scoring/nps.py (tabla_rutas y _lectura) con los umbrales de fase3_scoring/config.py: si cambian allí, hay que
// cambiarlos aquí. Sin React ni imports, para probarla con node (codigo/tests/test_interfaz.py la compara con nps.py).

export const UMBRAL_NPS = 0.33;
export const MIN_PARES_CON_SIGNO = 3;
export const MIN_COBERTURA = 0.3;

// Signo que puede fijar a mano una persona experta
export type Criterio = '+1' | '-1' | 'neutro';

// Lo que hace falta de cada par (gen, ruta) de la Fase 3
export interface ParRuta {
  Gen: string;
  Direccion: string;
  Signo_par: string;
  Estado_par: string;
  Origen: string;
  Motivos: string | null;
  Log2FC: number | null;
  Contribucion: number;
}

// Lo que se recalcula de la fila de la ruta
export interface LecturaRuta {
  NPS: number | null;
  Lectura: string;
  NPS_log2FC?: number | null;
  Lectura_log2FC?: string | null;
  Sensible_al_peso?: string;
  n_activan: number;
  n_inhiben: number;
  n_pendiente: number;
  Cobertura: number;
}

// round(v, 3) de Python: el número de tres decimales más cercano al valor exacto; un empate exacto, al par. toFixed hace
// lo mismo salvo en los empates (los lleva hacia fuera), que con tres decimales solo se dan en los múltiplos impares de
// 1/16 (0,5625 → 0,562). Así la pantalla y los Excels de la Fase 3 dan el mismo número.
export const redondear = (v: number | null): number | null => {
  if (v === null) return null;
  const dieciseisavos = v * 16;
  if (Number.isInteger(dieciseisavos) && dieciseisavos % 2 !== 0) {
    const abajo = Math.floor(v * 1000);
    return (abajo % 2 === 0 ? abajo : abajo + 1) / 1000;
  }
  return Number(v.toFixed(3));
};

export const aplicarCriterio = <P extends ParRuta>(pares: P[], criterio: Record<string, Criterio>): P[] =>
  pares.map((g) => {
    const s = criterio[g.Gen];
    if (!s) return g;
    const direccion = g.Direccion === 'up' ? 1 : -1;
    return {
      ...g, Signo_par: s, Estado_par: 'resuelto', Origen: 'Experto', Motivos: 'criterio_experto',
      Contribucion: s === 'neutro' ? 0 : (s === '+1' ? 1 : -1) * direccion,
    };
  });

export const recalcularRuta = <R extends LecturaRuta>(r: R, pares: ParRuta[]): R => {
  const resueltos = pares.filter((g) => g.Estado_par === 'resuelto');
  const conSigno = resueltos.filter((g) => g.Signo_par === '+1' || g.Signo_par === '-1');
  const neutros = resueltos.filter((g) => g.Signo_par === 'neutro');
  const cobertura = pares.length ? (conSigno.length + neutros.length) / pares.length : 0;
  const lectura = (v: number | null) => {
    if (v === null || conSigno.length < MIN_PARES_CON_SIGNO || cobertura < MIN_COBERTURA) return 'insuficiente';
    return v >= UMBRAL_NPS ? 'activada' : v <= -UMBRAL_NPS ? 'inhibida' : 'mixta';
  };
  const peso = (g: ParRuta) => (g.Log2FC === null || g.Log2FC === undefined ? 1 : Math.abs(Number(g.Log2FC)));
  const suma = (f: (g: ParRuta) => number) => conSigno.reduce((a, g) => a + f(g), 0);
  const nps = conSigno.length ? suma((g) => Number(g.Contribucion)) / conSigno.length : null;
  const conLog2fc = Boolean(r.Lectura_log2FC);
  const npsFc = conLog2fc && conSigno.length ? suma((g) => Number(g.Contribucion) * peso(g)) / suma(peso) : null;
  const lec = lectura(nps);
  const lecFc = conLog2fc ? lectura(npsFc) : '';
  return {
    ...r,
    NPS: redondear(nps), Lectura: lec, NPS_log2FC: redondear(npsFc), Lectura_log2FC: lecFc,
    Sensible_al_peso: conLog2fc ? (lec !== lecFc ? 'sí' : 'no') : '',
    n_activan: pares.filter((g) => Number(g.Contribucion) > 0).length,
    n_inhiben: pares.filter((g) => Number(g.Contribucion) < 0).length,
    n_pendiente: pares.filter((g) => g.Estado_par === 'pendiente').length,
    Cobertura: redondear(cobertura) ?? 0,
  };
};

// Cuántos genes a favor tendrían que dejar de contar para que la ruta perdiera su lectura (activada o inhibida)
export const genesParaCambiar = (aFavor: number, enContra: number) => {
  for (let k = 1; k <= aFavor; k++) {
    const total = aFavor - k + enContra;
    if (total < MIN_PARES_CON_SIGNO || (aFavor - k - enContra) / total < UMBRAL_NPS) return k;
  }
  return aFavor;
};
