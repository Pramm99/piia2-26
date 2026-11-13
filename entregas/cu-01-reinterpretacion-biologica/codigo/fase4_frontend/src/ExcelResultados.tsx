import { useEffect, useRef, useState, type ChangeEvent, type CSSProperties } from 'react';
import { ChevronDown, ChevronRight, Download, Eraser, FilePlus2, FileSpreadsheet, FolderOpen, Trash2, X } from 'lucide-react';
import { colorLectura, formatoNPS, loadXLSX, mensaje, type Fila, type Libro } from './comun';

// Excel de resultados de la Fase 3: va acumulando una fila por ruta ejecutada (hoja Rutas) y sus genes (hoja Genes).
// Se puede empezar con uno vacío o con uno que ya tenga rutas; si la ruta ya estaba, su fila se sustituye.
// Con Chrome o Edge se guarda directamente en el fichero elegido; en otros navegadores, con «Descargar».

const HOJA_RUTAS = 'Rutas';
const HOJA_GENES = 'Genes';
const COLUMNAS_RUTAS = ['Fecha', 'GO_ID', 'Ruta_Nombre', 'Listas', 'Lectura', 'NPS', 'NPS_log2FC', 'Lectura_log2FC',
  'Sensible_al_peso', 'n_total', 'n_activan', 'n_inhiben', 'n_neutros', 'n_no_concluyente', 'n_sin_evidencia',
  'n_pendiente', 'Cobertura', 'Genes_activan', 'Genes_inhiben'];
const COLUMNAS_GENES = ['GO_ID', 'Ruta_Nombre', 'Gen', 'Direccion', 'Log2FC', 'Signo_par', 'Estado_par', 'Origen',
  'Contribucion', 'Motivos', 'Votos', 'PMIDs_consultados'];

// API de acceso a ficheros de Chrome/Edge: permite volver a escribir en el mismo fichero
interface Escritura {
  write: (datos: ArrayBuffer) => Promise<void>;
  close: () => Promise<void>;
}
interface Manejador {
  name: string;
  getFile: () => Promise<File>;
  createWritable: () => Promise<Escritura>;
  requestPermission?: (opts: { mode: 'readwrite' }) => Promise<string>;
}
interface OpcionesSelector {
  types?: { description: string; accept: Record<string, string[]> }[];
  suggestedName?: string;
}
type VentanaFicheros = Window & {
  showOpenFilePicker?: (opts?: OpcionesSelector) => Promise<Manejador[]>;
  showSaveFilePicker?: (opts?: OpcionesSelector) => Promise<Manejador>;
};
const TIPOS = [{ description: 'Excel', accept: { 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'] } }];

interface Acumulado {
  nombre: string;
  libro: Libro;
  rutas: Fila[];
  genes: Fila[];
  manejador: Manejador | null; // null: no se puede escribir en el fichero, hay que descargarlo
  sinGuardar: boolean;
  version: number;
  ultima?: string;
}

export interface ResultadoParaExcel {
  rutas: unknown[];
  pares: unknown[];
}

const limpio = (v: unknown) => (v === null || v === undefined || (typeof v === 'number' && Number.isNaN(v)) ? '' : v);
const columnas = (f: Fila, cols: string[]) => Object.fromEntries(cols.map((c) => [c, limpio(f[c])]));
const numero = (v: unknown) => (v === '' || v === null || v === undefined || Number.isNaN(Number(v)) ? null : Number(v));

const añadirResultado = (acc: Acumulado, res: ResultadoParaExcel): Acumulado => {
  const ruta = res.rutas[0] as Fila;
  const go = String(ruta.GO_ID);
  const fila = columnas({ ...ruta, Fecha: new Date().toLocaleString('es-ES') }, COLUMNAS_RUTAS);
  const genes = (res.pares as Fila[]).filter((p) => p.GO_ID === go).map((p) => columnas(p, COLUMNAS_GENES));
  return {
    ...acc,
    rutas: [...acc.rutas.filter((r) => String(r.GO_ID) !== go), fila],
    genes: [...acc.genes.filter((g) => String(g.GO_ID) !== go), ...genes],
    sinGuardar: true,
    version: acc.version + 1,
    ultima: go,
  };
};

const leer = async (datos: ArrayBuffer, nombre: string) => {
  const XLSX = await loadXLSX();
  const libro = XLSX.read(datos, { type: 'array' });
  const hoja = (h: string) => (libro.Sheets[h] ? XLSX.utils.sheet_to_json(libro.Sheets[h], { defval: '' }) : []);
  const rutas = hoja(HOJA_RUTAS);
  if (rutas.length && !('GO_ID' in rutas[0])) {
    throw new Error(`${nombre}: la hoja «${HOJA_RUTAS}» no tiene la columna GO_ID, así que no parece un Excel de resultados.`);
  }
  return { libro, rutas, genes: hoja(HOJA_GENES) };
};

// Escribe las hojas Rutas y Genes; el resto de hojas del libro se conserva tal cual
const aBytes = async (acc: Acumulado) => {
  const XLSX = await loadXLSX();
  const hojas: [string, Fila[], string[]][] = [[HOJA_RUTAS, acc.rutas, COLUMNAS_RUTAS], [HOJA_GENES, acc.genes, COLUMNAS_GENES]];
  for (const [nombre, filas, cols] of hojas) {
    if (!acc.libro.SheetNames.includes(nombre)) acc.libro.SheetNames.push(nombre);
    acc.libro.Sheets[nombre] = XLSX.utils.json_to_sheet(filas, { header: cols });
  }
  return XLSX.write(acc.libro, { type: 'array', bookType: 'xlsx' });
};

const boton: CSSProperties = { padding: '6px 12px', borderRadius: '8px', border: '1px solid var(--c-334155)', backgroundColor: 'var(--c-1e293b)', color: 'var(--c-f8fafc)', fontSize: '12px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px' };

export default function ExcelResultados({ resultado }: { resultado: ResultadoParaExcel | null }) {
  const [acc, setAcc] = useState<Acumulado | null>(null);
  const [nota, setNota] = useState<{ tipo: 'ok' | 'err'; texto: string } | null>(null);
  const [confirmarLimpiar, setConfirmarLimpiar] = useState(false);
  const [abierta, setAbierta] = useState<string | null>(null);
  const procesado = useRef<ResultadoParaExcel | null>(null);
  const entrada = useRef<HTMLInputElement>(null);
  const ventana = window as VentanaFicheros;
  const puedeEscribir = Boolean(ventana.showOpenFilePicker && ventana.showSaveFilePicker);

  // Cada ruta que se ejecuta se añade al Excel (o sustituye a la que ya estaba)
  useEffect(() => {
    if (!resultado || procesado.current === resultado) return;
    procesado.current = resultado;
    setAcc((prev) => (prev ? añadirResultado(prev, resultado) : prev));
    setNota(null); // el estado de la última ruta guardada sale en la cabecera de la vista previa
  }, [resultado]);

  // Si se puede escribir en el fichero, se guarda solo después de cada cambio
  useEffect(() => {
    if (!acc || !acc.sinGuardar || !acc.manejador) return;
    const { version, manejador, nombre } = acc;
    (async () => {
      try {
        const bytes = await aBytes(acc);
        const escritura = await manejador.createWritable();
        await escritura.write(bytes);
        await escritura.close();
        setAcc((prev) => (prev && prev.version === version ? { ...prev, sinGuardar: false } : prev));
      } catch (err) {
        setNota({ tipo: 'err', texto: `No se pudo guardar en ${nombre}: ${mensaje(err)}. Usa «Descargar».` });
      }
    })();
  }, [acc]);

  const empezar = (base: Omit<Acumulado, 'version' | 'sinGuardar' | 'ultima'>, sinGuardar: boolean) => {
    let nuevo: Acumulado = { ...base, sinGuardar, version: 0 };
    let añadida = '';
    // Si ya se ha ejecutado una ruta, se añade al Excel que se acaba de poner
    if (resultado) {
      nuevo = añadirResultado(nuevo, resultado);
      procesado.current = resultado;
      añadida = ` Se ha añadido la ruta que acabas de ejecutar (${nuevo.ultima}).`;
    }
    setAcc(nuevo);
    setConfirmarLimpiar(false);
    setNota({ tipo: 'ok', texto: `${base.nombre}: ${base.rutas.length === 1 ? '1 ruta guardada' : `${base.rutas.length} rutas guardadas`}.${añadida}` });
  };

  const abrir = async () => {
    setNota(null);
    if (!ventana.showOpenFilePicker) {
      entrada.current?.click();
      return;
    }
    try {
      const [manejador] = await ventana.showOpenFilePicker({ types: TIPOS });
      if (manejador.requestPermission) await manejador.requestPermission({ mode: 'readwrite' });
      const fichero = await manejador.getFile();
      const { libro, rutas, genes } = await leer(await fichero.arrayBuffer(), fichero.name);
      empezar({ nombre: fichero.name, libro, rutas, genes, manejador }, false);
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') return;
      setNota({ tipo: 'err', texto: mensaje(err) });
    }
  };

  // Sin la API de ficheros: se lee el Excel subido y los cambios se descargan
  const abrirSubido = async (e: ChangeEvent<HTMLInputElement>) => {
    const fichero = e.target.files?.[0];
    e.target.value = '';
    if (!fichero) return;
    try {
      const { libro, rutas, genes } = await leer(await fichero.arrayBuffer(), fichero.name);
      empezar({ nombre: fichero.name, libro, rutas, genes, manejador: null }, false);
    } catch (err) {
      setNota({ tipo: 'err', texto: mensaje(err) });
    }
  };

  const crear = async () => {
    setNota(null);
    try {
      const XLSX = await loadXLSX();
      const libro = XLSX.utils.book_new();
      if (ventana.showSaveFilePicker) {
        const manejador = await ventana.showSaveFilePicker({ suggestedName: 'resultados_rutas.xlsx', types: TIPOS });
        empezar({ nombre: manejador.name, libro, rutas: [], genes: [], manejador }, true);
      } else {
        empezar({ nombre: 'resultados_rutas.xlsx', libro, rutas: [], genes: [], manejador: null }, true);
      }
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') return;
      setNota({ tipo: 'err', texto: mensaje(err) });
    }
  };

  const descargar = async () => {
    if (!acc) return;
    const bytes = await aBytes(acc);
    const url = URL.createObjectURL(new Blob([bytes], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' }));
    const a = document.createElement('a');
    a.href = url;
    a.download = acc.nombre.endsWith('.xlsx') ? acc.nombre : `${acc.nombre}.xlsx`;
    a.click();
    URL.revokeObjectURL(url);
    if (!acc.manejador) setAcc({ ...acc, sinGuardar: false });
  };

  const cambiar = (rutas: Fila[], genes: Fila[], texto: string) => {
    if (!acc) return;
    setAcc({ ...acc, rutas, genes, sinGuardar: true, version: acc.version + 1, ultima: undefined });
    setNota({ tipo: 'ok', texto });
  };

  const estado = !acc
    ? ''
    : acc.manejador
      ? acc.sinGuardar ? 'Guardando…' : '✓ Guardado en el fichero'
      : acc.sinGuardar ? 'Cambios sin descargar' : '✓ Descargado';

  // Vista previa: la última ruta añadida, primero
  const filas = acc ? [...acc.rutas].reverse() : [];

  return (
    <section style={{ backgroundColor: 'var(--c-0f172a)', border: '1px solid var(--c-1e293b)', borderRadius: '16px', padding: '20px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
      <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'space-between', alignItems: 'center', gap: '12px' }}>
        <div>
          <h2 style={{ margin: '0 0 4px 0', fontSize: '15px', fontWeight: 'bold', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <FileSpreadsheet size={18} color="var(--c-2dd4bf)" />
            <span>Fase 3 · Excel de resultados</span>
          </h2>
          <p style={{ margin: 0, fontSize: '12px', color: 'var(--c-94a3b8)', maxWidth: '900px' }}>
            Pon un Excel vacío o uno con rutas ya buscadas: cada ruta que ejecutes se añade sola (si ya estaba, se actualiza).
            Se guarda el resultado automático, sin los cambios de «Tu criterio».
            {puedeEscribir ? ' Los cambios se escriben directamente en el fichero.' : ' En este navegador no se puede escribir en el fichero: usa «Descargar» para guardar los cambios.'}
          </p>
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
          <input ref={entrada} type="file" accept=".xlsx" onChange={abrirSubido} style={{ display: 'none' }} />
          <button onClick={abrir} style={boton} title="Excel vacío o con rutas ya buscadas">
            <FolderOpen size={14} color="var(--c-2dd4bf)" />
            <span>{acc ? 'Cambiar de Excel' : 'Abrir Excel'}</span>
          </button>
          <button onClick={crear} style={boton}>
            <FilePlus2 size={14} color="var(--c-2dd4bf)" />
            <span>Crear Excel nuevo</span>
          </button>
          {acc && (
            <>
              <button onClick={descargar} style={boton} title="Guardar una copia">
                <Download size={14} />
                <span>Descargar</span>
              </button>
              {confirmarLimpiar ? (
                <>
                  <button
                    onClick={() => {
                      setConfirmarLimpiar(false);
                      cambiar([], [], `${acc.nombre} se ha vaciado: las próximas rutas empiezan un Excel limpio.`);
                    }}
                    style={{ ...boton, borderColor: 'var(--c-fda4af)', color: 'var(--c-fda4af)' }}
                  >
                    <Eraser size={14} />
                    <span>Sí, borrar las {acc.rutas.length} rutas</span>
                  </button>
                  <button onClick={() => setConfirmarLimpiar(false)} style={boton}>Cancelar</button>
                </>
              ) : (
                <button onClick={() => setConfirmarLimpiar(true)} style={boton} title="Borra todas las rutas del Excel">
                  <Eraser size={14} color="var(--c-fda4af)" />
                  <span>Limpiar Excel</span>
                </button>
              )}
              <button
                onClick={() => {
                  setAcc(null);
                  setNota(null);
                  setConfirmarLimpiar(false);
                }}
                style={boton}
                title="Deja de usar este Excel (no lo borra)"
              >
                <X size={14} />
                <span>Quitar</span>
              </button>
            </>
          )}
        </div>
      </div>

      {nota && (
        <div style={{ fontSize: '12px', color: nota.tipo === 'err' ? 'var(--c-fda4af)' : 'var(--c-5eead4)' }}>{nota.texto}</div>
      )}

      {!acc ? (
        <div style={{ fontSize: '12px', color: 'var(--c-64748b)', padding: '10px', textAlign: 'center', border: '1px dashed var(--c-334155)', borderRadius: '10px' }}>
          Sin Excel de resultados: las rutas que ejecutes no se guardan en ninguno.
        </div>
      ) : (
        <div style={{ border: '1px solid var(--c-1e293b)', borderRadius: '10px', overflow: 'hidden' }}>
          <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'space-between', gap: '8px', padding: '8px 12px', backgroundColor: 'var(--c-020617)', fontSize: '12px' }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <FileSpreadsheet size={14} color="var(--c-2dd4bf)" />
              <strong>{acc.nombre}</strong>
              <span style={{ color: 'var(--c-64748b)' }}>· {acc.rutas.length} rutas · {acc.genes.length} genes</span>
              {acc.ultima && <span style={{ color: 'var(--c-34d399)' }}>· última guardada: {acc.ultima}</span>}
            </span>
            <span style={{ color: acc.sinGuardar ? 'var(--c-fbbf24)' : 'var(--c-34d399)' }}>{estado}</span>
          </div>
          {filas.length === 0 ? (
            <div style={{ fontSize: '12px', color: 'var(--c-64748b)', padding: '14px', textAlign: 'center' }}>
              El Excel está vacío: ejecuta una ruta y aparecerá aquí.
            </div>
          ) : (
            <div style={{ maxHeight: '320px', overflowY: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px', textAlign: 'left' }}>
                <thead style={{ position: 'sticky', top: 0, backgroundColor: 'var(--c-020617)' }}>
                  <tr style={{ color: 'var(--c-94a3b8)', borderBottom: '1px solid var(--c-1e293b)' }}>
                    <th style={{ padding: '7px 10px', width: '20px' }}></th>
                    <th style={{ padding: '7px 10px' }}>GO_ID</th>
                    <th style={{ padding: '7px 10px' }}>Ruta</th>
                    <th style={{ padding: '7px 10px' }}>Lectura</th>
                    <th style={{ padding: '7px 10px' }}>NPS</th>
                    <th style={{ padding: '7px 10px' }}>Genes (activan · inhiben · total)</th>
                    <th style={{ padding: '7px 10px' }}>Fecha</th>
                    <th style={{ padding: '7px 10px', width: '30px' }}></th>
                  </tr>
                </thead>
                <tbody>
                  {filas.map((r) => {
                    const go = String(r.GO_ID);
                    const lectura = String(r.Lectura || '');
                    const nps = numero(r.NPS);
                    const abiertaFila = abierta === go;
                    const genesRuta = acc.genes.filter((g) => String(g.GO_ID) === go);
                    return (
                      <FilaRuta
                        key={go}
                        go={go}
                        r={r}
                        lectura={lectura}
                        nps={nps}
                        nueva={acc.ultima === go}
                        abierta={abiertaFila}
                        genes={genesRuta}
                        onAbrir={() => setAbierta(abiertaFila ? null : go)}
                        onQuitar={() => cambiar(
                          acc.rutas.filter((x) => String(x.GO_ID) !== go),
                          acc.genes.filter((x) => String(x.GO_ID) !== go),
                          `${go} quitada del Excel.`,
                        )}
                      />
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </section>
  );
}

// Una ruta del Excel en la vista previa; al pulsarla se ven sus genes
function FilaRuta({ go, r, lectura, nps, nueva, abierta, genes, onAbrir, onQuitar }: {
  go: string; r: Fila; lectura: string; nps: number | null; nueva: boolean; abierta: boolean; genes: Fila[];
  onAbrir: () => void; onQuitar: () => void;
}) {
  const color = colorLectura(lectura);
  return (
    <>
      <tr
        onClick={onAbrir}
        style={{ borderBottom: '1px solid var(--c-1e293b)', cursor: 'pointer', backgroundColor: nueva ? 'color-mix(in srgb, var(--c-2dd4bf) 10%, transparent)' : 'transparent' }}
      >
        <td style={{ padding: '7px 10px', color: 'var(--c-64748b)' }}>{abierta ? <ChevronDown size={13} /> : <ChevronRight size={13} />}</td>
        <td style={{ padding: '7px 10px', fontFamily: 'monospace', fontWeight: 'bold', color: 'var(--c-2dd4bf)' }}>
          {go}
          {nueva && <span style={{ marginLeft: '6px', fontSize: '10px', fontFamily: 'inherit', color: 'var(--c-34d399)' }}>nueva</span>}
        </td>
        <td style={{ padding: '7px 10px' }}>{String(r.Ruta_Nombre || '')}</td>
        <td style={{ padding: '7px 10px' }}>
          <span style={{ fontWeight: 'bold', textTransform: 'uppercase', fontSize: '11px', color, border: `1px solid ${color}`, borderRadius: '4px', padding: '1px 6px' }}>{lectura || '—'}</span>
        </td>
        <td style={{ padding: '7px 10px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <div style={{ position: 'relative', width: '80px', height: '6px', borderRadius: '3px', backgroundColor: 'var(--c-1e293b)' }}>
              <div style={{ position: 'absolute', left: '50%', top: '-2px', bottom: '-2px', width: '1px', backgroundColor: 'var(--c-475569)' }} />
              {nps !== null && (
                <div style={{ position: 'absolute', top: 0, bottom: 0, left: `${Math.min(50, ((nps + 1) / 2) * 100)}%`, width: `${Math.abs(nps) * 50}%`, backgroundColor: color, borderRadius: '3px' }} />
              )}
            </div>
            <span style={{ fontFamily: 'monospace' }}>{formatoNPS(nps)}</span>
          </div>
        </td>
        <td style={{ padding: '7px 10px' }}>
          <span style={{ color: 'var(--c-34d399)' }}>{String(r.n_activan ?? '')}</span> · <span style={{ color: 'var(--c-f87171)' }}>{String(r.n_inhiben ?? '')}</span> · {String(r.n_total ?? '')}
        </td>
        <td style={{ padding: '7px 10px', color: 'var(--c-64748b)', whiteSpace: 'nowrap' }}>{String(r.Fecha || '')}</td>
        <td style={{ padding: '7px 10px' }} onClick={(e) => e.stopPropagation()}>
          <button onClick={onQuitar} title={`Quitar ${go} del Excel`} style={{ background: 'none', border: 'none', color: 'var(--c-64748b)', cursor: 'pointer', display: 'flex' }}>
            <Trash2 size={14} />
          </button>
        </td>
      </tr>
      {abierta && (
        <tr style={{ borderBottom: '1px solid var(--c-1e293b)' }}>
          <td></td>
          <td colSpan={7} style={{ padding: '6px 10px 10px 10px' }}>
            {genes.length === 0 ? (
              <span style={{ fontSize: '12px', color: 'var(--c-64748b)' }}>Este Excel no tiene los genes de la ruta.</span>
            ) : (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '5px' }}>
                {genes.map((g) => {
                  const c = Number(g.Contribucion);
                  const col = c > 0 ? 'var(--c-34d399)' : c < 0 ? 'var(--c-f87171)' : 'var(--c-64748b)';
                  return (
                    <span key={String(g.Gen)} title={`${String(g.Signo_par)} · ${String(g.Estado_par)} · ${String(g.Origen)}`} style={{ fontSize: '11px', fontFamily: 'monospace', padding: '2px 6px', borderRadius: '4px', border: `1px solid ${col}`, color: col }}>
                      {g.Direccion === 'up' ? '▲' : '▼'} {String(g.Gen)}
                    </span>
                  );
                })}
                <span style={{ fontSize: '11px', color: 'var(--c-64748b)', alignSelf: 'center' }}>
                  verde: empuja hacia activada · rojo: hacia inhibida · gris: no cuenta
                </span>
              </div>
            )}
          </td>
        </tr>
      )}
    </>
  );
}
