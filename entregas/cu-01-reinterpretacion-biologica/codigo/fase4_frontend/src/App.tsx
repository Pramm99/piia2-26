import React, { useState, useMemo, useEffect, useRef } from 'react';
import {
  UploadCloud,
  FileSpreadsheet,
  Search,
  Info,
  Microscope,
  Circle,
  CheckCircle2,
  Download,
  Play,
  Loader2,
  X
} from 'lucide-react';

const API_URL = 'http://127.0.0.1:8000';

// Lo mínimo de SheetJS que se usa (se carga desde el CDN solo si se sube un Excel)
interface LibXLSX {
  read: (data: ArrayBuffer, opts: { type: 'array' }) => { SheetNames: string[]; Sheets: Record<string, unknown> };
  utils: { sheet_to_json: (hoja: unknown) => Record<string, unknown>[] };
}
type VentanaConXLSX = Window & { XLSX?: LibXLSX };

const mensaje = (err: unknown) => (err instanceof Error ? err.message : String(err));

const loadXLSX = (): Promise<LibXLSX> => {
  return new Promise((resolve, reject) => {
    const w = window as VentanaConXLSX;
    if (w.XLSX) {
      resolve(w.XLSX);
      return;
    }
    const script = document.createElement('script');
    script.src = 'https://cdn.jsdelivr.net/npm/xlsx@0.18.5/dist/xlsx.full.min.js';
    script.onload = () => resolve((window as VentanaConXLSX).XLSX as LibXLSX);
    script.onerror = () => reject(new Error('No se pudo cargar la librería XLSX'));
    document.head.appendChild(script);
  });
};

const descargarBase64Excel = (b64: string, filename: string) => {
  const byteCharacters = atob(b64);
  const byteNumbers = new Array(byteCharacters.length);
  for (let i = 0; i < byteCharacters.length; i++) {
    byteNumbers[i] = byteCharacters.charCodeAt(i);
  }
  const blob = new Blob([new Uint8Array(byteNumbers)], {
    type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
};

// Una ruta GO de CIMUS: puede estar en las dos listas (genes up y genes down)
interface Ruta {
  GO_ID: string;
  Descripcion: string;
  Genes_up: string;
  Genes_down: string;
}

interface GeneContribution {
  Gen: string;
  GO_ID: string;
  Ruta_Nombre: string;
  Direccion: string;
  Signo_par: string;
  Estado_par: string;
  Motivos: string | null;
  Origen: string;
  Votos: string | null;
  Contribucion: number;
  Freno_retroalimentacion: boolean;
}

interface PathwayResult {
  GO_ID: string;
  Ruta_Nombre: string;
  Listas: string;
  NPS: number | null;
  Lectura: string;
  NPS_log2FC?: number | null;
  Lectura_log2FC?: string | null;
  Sensible_al_peso?: string;
  n_total: number;
  n_activan: number;
  n_inhiben: number;
  n_pendiente: number;
  Cobertura: number;
}

interface Resultado {
  rutas: PathwayResult[];
  pares: GeneContribution[];
  llm: { llamadas: number; reutilizadas: number; pendientes: number; tokens: number };
  tiempos: { fase1: number; fase2: number; fase3: number };
  carpeta: string;
  excel_b64: string;
  nombre_excel: string;
}

const genes = (s: string) => s.split('/').map((g) => g.trim()).filter(Boolean);

const formatoNPS = (v: number | null | undefined) =>
  v === null || v === undefined ? 'N/A' : v > 0 ? `+${v.toFixed(2)}` : v.toFixed(2);

const colorLectura = (l: string) => (l === 'activada' ? '#34d399' : l === 'inhibida' ? '#f87171' : '#fbbf24');

const PASOS = [
  { step: 1, title: 'Fase 1 · Ingesta GO & PubMed', desc: 'Subárbol GO, triaje y descarga de abstracts' },
  { step: 2, title: 'Fase 2 · Inferencia LLM', desc: 'Gemini, con gpt-oss solo de respaldo; citas verificadas' },
  { step: 3, title: 'Fase 3 · Scoring NPS', desc: 'Signo de cada gen y Net Pathway Score' },
];

export default function App() {
  const [backendOnline, setBackendOnline] = useState<boolean>(false);

  const [rutas, setRutas] = useState<Ruta[]>([]);
  const [origenRutas, setOrigenRutas] = useState<string>('');
  const [defaultLista, setDefaultLista] = useState<'Activada' | 'Suprimida'>('Activada');
  const [search, setSearch] = useState('');
  const [seleccion, setSeleccion] = useState<string | null>(null);
  const [confirmando, setConfirmando] = useState(false);

  const [isRunning, setIsRunning] = useState(false);
  const [currentStep, setCurrentStep] = useState<number>(0);
  const [segundos, setSegundos] = useState<number>(0);
  const [feedback, setFeedback] = useState<{ type: 'info' | 'ok' | 'err'; msg: string } | null>(null);
  const [resultado, setResultado] = useState<Resultado | null>(null);
  const inicioRef = useRef<number>(0);

  useEffect(() => {
    const check = async () => {
      try {
        const res = await fetch(`${API_URL}/salud`);
        setBackendOnline(res.ok);
      } catch {
        setBackendOnline(false);
      }
    };
    check();
    const id = setInterval(check, 5000);
    return () => clearInterval(id);
  }, []);

  // Al conectar, se cargan las rutas de los Excels de CIMUS (codigo/tools_cimus/), si no se ha subido otro
  useEffect(() => {
    if (!backendOnline || rutas.length > 0) return;
    fetch(`${API_URL}/rutas`)
      .then((r) => r.json())
      .then((d) => {
        if (!d.ok) throw new Error(d.error);
        setRutas(d.rutas);
        setOrigenRutas('Excels de CIMUS (codigo/tools_cimus/)');
      })
      .catch((err) => setFeedback({ type: 'err', msg: mensaje(err) }));
  }, [backendOnline, rutas.length]);

  // Mientras se ejecuta, se consulta al puente qué fase va por
  useEffect(() => {
    if (!isRunning) return;
    const id = setInterval(async () => {
      setSegundos(Math.round((Date.now() - inicioRef.current) / 1000));
      try {
        const d = await (await fetch(`${API_URL}/estado`)).json();
        if (d.estado === 'ejecutando') {
          setCurrentStep(d.fase);
        } else if (d.estado === 'terminado') {
          const r: Resultado = d.resultado;
          setResultado(r);
          setCurrentStep(4);
          setIsRunning(false);
          const pend = r.llm.pendientes
            ? ` ⚠️ ${r.llm.pendientes} preguntas quedaron pendientes (cupo del LLM agotado): vuelve a ejecutar la ruta más tarde.`
            : '';
          setFeedback({
            type: 'ok',
            msg: `${d.GO_ID} ejecutada en ${r.tiempos.fase1 + r.tiempos.fase2 + r.tiempos.fase3} s: ${r.llm.llamadas} llamadas al LLM, ${r.llm.reutilizadas} respuestas reutilizadas del registro.${pend}`,
          });
        } else if (d.estado === 'error') {
          setIsRunning(false);
          setCurrentStep(0);
          setFeedback({ type: 'err', msg: `Error en la Fase ${d.fase}: ${d.error}` });
        }
      } catch {
        // el puente puede tardar en responder mientras trabaja: se reintenta en el siguiente ciclo
      }
    }, 1500);
    return () => clearInterval(id);
  }, [isRunning]);

  const filtradas = useMemo(() => {
    const q = search.toLowerCase();
    return rutas.filter(
      (r) =>
        r.GO_ID.toLowerCase().includes(q) ||
        r.Descripcion.toLowerCase().includes(q) ||
        `${r.Genes_up}/${r.Genes_down}`.toLowerCase().includes(q)
    );
  }, [rutas, search]);

  const rutaSel = useMemo(() => rutas.find((r) => r.GO_ID === seleccion) || null, [rutas, seleccion]);

  const rutaRes = resultado?.rutas[0];
  const paresRes = useMemo(
    () => (resultado ? resultado.pares.filter((p) => p.GO_ID === rutaRes?.GO_ID) : []),
    [resultado, rutaRes]
  );

  // Excel propio de CIMUS (ID, Description, geneID): la lista sale del nombre del fichero o del selector
  const handleExcelUpload = async (e: React.ChangeEvent<HTMLInputElement>, append: boolean) => {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (!file) return;
    try {
      const XLSX = await loadXLSX();
      const wb = XLSX.read(await file.arrayBuffer(), { type: 'array' });
      const rows = XLSX.utils.sheet_to_json(wb.Sheets[wb.SheetNames[0]]);
      if (!rows.length || !('ID' in rows[0]) || !('Description' in rows[0]) || !('geneID' in rows[0])) {
        throw new Error('El Excel debe contener las columnas obligatorias: ID, Description y geneID.');
      }
      const lista = file.name.toLowerCase().includes('suprimid') ? 'Suprimida' : defaultLista;
      const campo = lista === 'Activada' ? 'Genes_up' : 'Genes_down';
      const base: Record<string, Ruta> = {};
      if (append) rutas.forEach((r) => (base[r.GO_ID] = { ...r }));
      rows.forEach((r) => {
        const id = String(r.ID || '').trim();
        if (!id) return;
        base[id] = base[id] || { GO_ID: id, Descripcion: String(r.Description || '').trim(), Genes_up: '', Genes_down: '' };
        base[id][campo] = String(r.geneID || '').trim();
      });
      setRutas(Object.values(base).sort((a, b) => a.GO_ID.localeCompare(b.GO_ID)));
      setOrigenRutas(append ? `${origenRutas} + ${file.name}` : file.name);
      setSeleccion(null);
      setFeedback({ type: 'ok', msg: `${rows.length} rutas leídas de ${file.name} (genes ${lista === 'Activada' ? 'up' : 'down'}). Elige una y ejecútala.` });
    } catch (err) {
      setFeedback({ type: 'err', msg: mensaje(err) });
    }
  };

  const ejecutarRuta = async () => {
    setConfirmando(false);
    if (!rutaSel) return;
    if (!backendOnline) {
      setFeedback({ type: 'err', msg: 'El motor Python local no está conectado. Ejecuta "python fase4_frontend/api_puente.py" desde codigo/.' });
      return;
    }
    try {
      const res = await fetch(`${API_URL}/ejecutar-ruta`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(rutaSel),
      });
      const d = await res.json();
      if (!res.ok || !d.ok) throw new Error(d.error || 'No se pudo lanzar la ejecución');
      inicioRef.current = Date.now();
      setSegundos(0);
      setResultado(null);
      setCurrentStep(1);
      setIsRunning(true);
      setFeedback({ type: 'info', msg: `Ejecutando ${rutaSel.GO_ID} (${rutaSel.Descripcion}): Fases 1 → 2 → 3...` });
    } catch (err) {
      setFeedback({ type: 'err', msg: mensaje(err) });
    }
  };

  return (
    <div style={{ minHeight: '100vh', backgroundColor: '#020617', color: '#f8fafc', display: 'flex', flexDirection: 'column', fontFamily: 'system-ui, -apple-system, sans-serif' }}>

      {/* HEADER */}
      <header style={{ borderBottom: '1px solid #1e293b', backgroundColor: '#0f172a', padding: '14px 24px', display: 'flex', flexWrap: 'wrap', justifyContent: 'space-between', alignItems: 'center', gap: '16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{ width: '40px', height: '40px', borderRadius: '10px', backgroundColor: '#14b8a6', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#020617' }}>
            <Microscope size={22} />
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
              <span style={{ fontSize: '16px', fontWeight: 'bold' }}>CU-01 PathScore Studio</span>
              <span style={{ fontSize: '11px', padding: '2px 8px', borderRadius: '999px', backgroundColor: 'rgba(20, 184, 166, 0.12)', color: '#5eead4', border: '1px solid rgba(20, 184, 166, 0.25)' }}>
                Células NK · Laringe y Faringe (HNSC)
              </span>
              <span style={{
                fontSize: '10px',
                padding: '2px 8px',
                borderRadius: '999px',
                backgroundColor: backendOnline ? 'rgba(16, 185, 129, 0.15)' : 'rgba(245, 158, 11, 0.15)',
                color: backendOnline ? '#6ee7b7' : '#fbbf24',
                border: `1px solid ${backendOnline ? '#059669' : '#b45309'}`
              }}>
                {backendOnline ? '● Motor Python conectado' : '○ Motor Python desconectado (ejecuta api_puente.py)'}
              </span>
            </div>
            <p style={{ margin: 0, fontSize: '12px', color: '#94a3b8' }}>
              Reinterpretación funcional de rutas biológicas scRNA-seq mediante Gene Ontology y LLMs verificados
            </p>
          </div>
        </div>
      </header>

      {/* FEEDBACK */}
      {feedback && (
        <div style={{
          backgroundColor: feedback.type === 'err' ? 'rgba(225, 29, 72, 0.15)' : 'rgba(20, 184, 166, 0.12)',
          borderBottom: `1px solid ${feedback.type === 'err' ? '#be123c' : '#0f766e'}`,
          padding: '8px 24px',
          fontSize: '12px',
          color: feedback.type === 'err' ? '#fda4af' : '#5eead4',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Info size={15} />
            <span>{feedback.msg}</span>
          </div>
          <button onClick={() => setFeedback(null)} style={{ background: 'none', border: 'none', color: 'inherit', cursor: 'pointer', fontSize: '11px' }}>Cerrar</button>
        </div>
      )}

      <main style={{ flex: 1, padding: '24px', maxWidth: '1720px', width: '100%', margin: '0 auto', boxSizing: 'border-box', display: 'flex', flexDirection: 'column', gap: '24px' }}>

        {/* PASO 1: ELEGIR UNA RUTA */}
        <section style={{ backgroundColor: '#0f172a', border: '1px solid #1e293b', borderRadius: '16px', padding: '20px' }}>
          <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'space-between', alignItems: 'center', gap: '16px', marginBottom: '16px' }}>
            <div>
              <h2 style={{ margin: '0 0 4px 0', fontSize: '15px', fontWeight: 'bold', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <FileSpreadsheet size={18} color="#2dd4bf" />
                <span>Paso 1 · Elegir la ruta que se va a ejecutar</span>
              </h2>
              <p style={{ margin: 0, fontSize: '12px', color: '#94a3b8' }}>
                Marca una ruta y confirma: se ejecutan seguidas las Fases 1, 2 y 3 con los genes de las dos listas de CIMUS.
                {origenRutas && <> Rutas de: <strong style={{ color: '#cbd5e1' }}>{origenRutas}</strong>.</>}
              </p>
            </div>

            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', alignItems: 'center' }}>
              <select
                value={defaultLista}
                onChange={(e) => setDefaultLista(e.target.value as 'Activada' | 'Suprimida')}
                style={{ padding: '7px 10px', fontSize: '12px', borderRadius: '8px', backgroundColor: '#020617', border: '1px solid #334155', color: '#cbd5e1' }}
              >
                <option value="Activada">Lista genes UP (Activada)</option>
                <option value="Suprimida">Lista genes DOWN (Suprimida)</option>
              </select>

              <label style={{ padding: '7px 14px', borderRadius: '8px', border: '1px solid #334155', backgroundColor: '#1e293b', color: '#f8fafc', fontSize: '12px', fontWeight: 500, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px' }}>
                <input type="file" accept=".xlsx,.xls,.csv" onChange={(e) => handleExcelUpload(e, false)} style={{ display: 'none' }} />
                <UploadCloud size={15} color="#2dd4bf" />
                <span>Subir otro Excel</span>
              </label>

              <label style={{ padding: '7px 14px', borderRadius: '8px', border: '1px solid #334155', backgroundColor: '#1e293b', color: '#cbd5e1', fontSize: '12px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px' }}>
                <input type="file" accept=".xlsx,.xls,.csv" onChange={(e) => handleExcelUpload(e, true)} style={{ display: 'none' }} />
                <span>+ Añadir 2ª Lista</span>
              </label>

              <button
                disabled={isRunning || !rutaSel}
                onClick={() => setConfirmando(true)}
                style={{
                  padding: '8px 18px',
                  borderRadius: '8px',
                  border: 'none',
                  backgroundColor: isRunning || !rutaSel ? '#0f766e' : '#14b8a6',
                  color: '#020617',
                  fontWeight: 'bold',
                  fontSize: '12px',
                  cursor: isRunning || !rutaSel ? 'not-allowed' : 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                }}
              >
                {isRunning ? <Loader2 size={16} /> : <Play size={16} />}
                <span>{isRunning ? `Ejecutando... (${segundos} s)` : rutaSel ? `Ejecutar ${rutaSel.GO_ID}` : 'Elige una ruta'}</span>
              </button>
            </div>
          </div>

          {/* BARRA DE PROGRESO (fase real que informa el puente) */}
          {(isRunning || currentStep > 0) && (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '12px', marginBottom: '16px', backgroundColor: '#020617', padding: '12px', borderRadius: '10px', border: '1px solid #1e293b' }}>
              {PASOS.map((s) => {
                const done = currentStep > s.step;
                const active = currentStep === s.step;
                return (
                  <div key={s.step} style={{ display: 'flex', alignItems: 'center', gap: '10px', opacity: currentStep >= s.step ? 1 : 0.4 }}>
                    {done ? <CheckCircle2 size={18} color="#34d399" /> : active ? <Loader2 size={18} color="#2dd4bf" /> : <div style={{ width: '18px', height: '18px', borderRadius: '50%', border: '2px solid #475569' }} />}
                    <div>
                      <div style={{ fontSize: '12px', fontWeight: 'bold', color: done ? '#6ee7b7' : active ? '#2dd4bf' : '#cbd5e1' }}>
                        {s.title}
                        {done && resultado && <span style={{ fontWeight: 'normal', color: '#64748b' }}> · {resultado.tiempos[`fase${s.step}` as 'fase1' | 'fase2' | 'fase3']} s</span>}
                      </div>
                      <div style={{ fontSize: '11px', color: '#64748b' }}>{s.desc}</div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px', gap: '12px' }}>
            <div style={{ position: 'relative', flex: 1, maxWidth: '420px' }}>
              <Search size={14} color="#64748b" style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)' }} />
              <input
                type="text"
                placeholder="Filtrar por GO_ID, nombre o gen..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                style={{ width: '100%', padding: '6px 10px 6px 30px', fontSize: '12px', borderRadius: '8px', backgroundColor: '#020617', border: '1px solid #1e293b', color: '#f8fafc', boxSizing: 'border-box' }}
              />
            </div>
            <span style={{ fontSize: '12px', color: '#94a3b8' }}>
              {filtradas.length} de {rutas.length} rutas{rutaSel && <> · elegida: <strong style={{ color: '#2dd4bf' }}>{rutaSel.GO_ID}</strong></>}
            </span>
          </div>

          <div style={{ maxHeight: '260px', overflowY: 'auto', border: '1px solid #1e293b', borderRadius: '10px' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px', textAlign: 'left' }}>
              <thead style={{ backgroundColor: '#020617', position: 'sticky', top: 0 }}>
                <tr style={{ borderBottom: '1px solid #1e293b', color: '#94a3b8' }}>
                  <th style={{ padding: '8px 10px', width: '36px' }}></th>
                  <th style={{ padding: '8px 10px' }}>GO_ID</th>
                  <th style={{ padding: '8px 10px' }}>Descripción</th>
                  <th style={{ padding: '8px 10px' }}>Genes up</th>
                  <th style={{ padding: '8px 10px' }}>Genes down</th>
                </tr>
              </thead>
              <tbody>
                {rutas.length === 0 && (
                  <tr>
                    <td colSpan={5} style={{ padding: '14px', color: '#64748b', textAlign: 'center' }}>
                      {backendOnline ? 'Cargando las rutas de CIMUS...' : 'Arranca el puente (api_puente.py) para cargar las rutas de CIMUS, o sube un Excel.'}
                    </td>
                  </tr>
                )}
                {filtradas.map((r) => {
                  const sel = r.GO_ID === seleccion;
                  return (
                    <tr
                      key={r.GO_ID}
                      onClick={() => !isRunning && setSeleccion(sel ? null : r.GO_ID)}
                      style={{ borderBottom: '1px solid rgba(30, 41, 59, 0.5)', backgroundColor: sel ? 'rgba(20, 184, 166, 0.08)' : 'transparent', cursor: isRunning ? 'default' : 'pointer' }}
                    >
                      <td style={{ padding: '8px 10px', textAlign: 'center' }}>{sel ? <CheckCircle2 size={15} color="#2dd4bf" /> : <Circle size={15} color="#475569" />}</td>
                      <td style={{ padding: '8px 10px', fontFamily: 'monospace', fontWeight: 'bold', color: '#2dd4bf' }}>{r.GO_ID}</td>
                      <td style={{ padding: '8px 10px', color: '#f1f5f9' }}>{r.Descripcion}</td>
                      {[r.Genes_up, r.Genes_down].map((g, i) => (
                        <td key={i} style={{ padding: '8px 10px', fontFamily: 'monospace', fontSize: '11px', color: i === 0 ? '#6ee7b7' : '#fda4af', maxWidth: '300px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }} title={g}>
                          {g ? <><strong>({genes(g).length})</strong> {g}</> : <span style={{ color: '#475569' }}>—</span>}
                        </td>
                      ))}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>

        {/* PASO 2: RESULTADO DE LA RUTA Y APORTACIÓN POR GEN */}
        <section style={{ backgroundColor: '#0f172a', border: '1px solid #1e293b', borderRadius: '16px', padding: '18px', display: 'flex', flexDirection: 'column' }}>
          {!rutaRes ? (
            <div style={{ color: '#64748b', fontSize: '13px', padding: '20px', textAlign: 'center' }}>
              {isRunning ? 'Ejecutando la ruta: el resultado aparecerá aquí al terminar la Fase 3.' : 'Aún no se ha ejecutado ninguna ruta.'}
            </div>
          ) : (
            <>
              <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'space-between', alignItems: 'flex-start', gap: '16px', borderBottom: '1px solid #1e293b', paddingBottom: '12px', marginBottom: '14px' }}>
                <div>
                  <span style={{ fontFamily: 'monospace', fontSize: '12px', color: '#2dd4bf', fontWeight: 'bold' }}>{rutaRes.GO_ID}</span>
                  <h3 style={{ margin: '2px 0 4px 0', fontSize: '16px', fontWeight: 'bold' }}>Paso 2 · {rutaRes.Ruta_Nombre}</h3>
                  <div style={{ fontSize: '11px', color: '#94a3b8', fontFamily: 'monospace' }}>
                    <span style={{ color: '#34d399' }}>{rutaRes.n_activan} activan</span> · <span style={{ color: '#f87171' }}>{rutaRes.n_inhiben} inhiben</span> · {rutaRes.n_total} genes · Cobertura {(Number(rutaRes.Cobertura || 0) * 100).toFixed(0)}%
                    {rutaRes.n_pendiente > 0 && <span style={{ color: '#fbbf24' }}> · {rutaRes.n_pendiente} pendientes de la Fase 2</span>}
                  </div>
                  <div style={{ fontSize: '11px', color: '#94a3b8', marginTop: '4px' }}>
                    Aportación de cada gen: <code>c = signo × dirección</code> · Con log2FC: NPS {formatoNPS(rutaRes.NPS_log2FC)} ({rutaRes.Lectura_log2FC || 'sin tabla'}){rutaRes.Sensible_al_peso === 'sí' && <strong style={{ color: '#fbbf24' }}> · sensible al peso</strong>}
                  </div>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                  <div style={{ textAlign: 'right' }}>
                    <span style={{ fontSize: '11px', color: '#94a3b8', display: 'block' }}>Lectura de la ruta</span>
                    <span style={{ fontSize: '17px', fontWeight: 'bold', textTransform: 'uppercase', color: colorLectura(rutaRes.Lectura) }}>
                      {rutaRes.Lectura} (NPS {formatoNPS(rutaRes.NPS)})
                    </span>
                  </div>
                  {resultado && (
                    <button
                      onClick={() => descargarBase64Excel(resultado.excel_b64, resultado.nombre_excel)}
                      style={{ padding: '6px 12px', fontSize: '11px', borderRadius: '6px', border: 'none', backgroundColor: '#14b8a6', color: '#020617', fontWeight: 'bold', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '5px' }}
                    >
                      <Download size={13} />
                      <span>Descargar Excel</span>
                    </button>
                  )}
                </div>
              </div>

              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px', textAlign: 'left' }}>
                  <thead style={{ backgroundColor: '#020617' }}>
                    <tr style={{ borderBottom: '1px solid #1e293b', color: '#94a3b8' }}>
                      <th style={{ padding: '9px' }}>Gen</th>
                      <th style={{ padding: '9px' }}>Expresión (d)</th>
                      <th style={{ padding: '9px' }}>Signo GO / LLM (s)</th>
                      <th style={{ padding: '9px' }}>Aportación (c)</th>
                      <th style={{ padding: '9px' }}>Estado</th>
                      <th style={{ padding: '9px' }}>Origen</th>
                      <th style={{ padding: '9px' }}>Evidencia / Motivos</th>
                    </tr>
                  </thead>
                  <tbody>
                    {paresRes.map((g, idx) => (
                      <tr key={idx} style={{ borderBottom: '1px solid rgba(30, 41, 59, 0.5)' }}>
                        <td style={{ padding: '9px', fontFamily: 'monospace', fontWeight: 'bold' }}>
                          {g.Gen}
                          {g.Freno_retroalimentacion && (
                            <span style={{ marginLeft: '6px', fontSize: '9px', padding: '1px 5px', borderRadius: '4px', backgroundColor: 'rgba(245, 158, 11, 0.2)', color: '#fbbf24' }}>Freno</span>
                          )}
                        </td>
                        <td style={{ padding: '9px', fontFamily: 'monospace', color: g.Direccion === 'up' ? '#6ee7b7' : '#fda4af' }}>{String(g.Direccion).toUpperCase()}</td>
                        <td style={{ padding: '9px', fontFamily: 'monospace', fontWeight: 'bold', color: g.Signo_par === '+1' ? '#2dd4bf' : g.Signo_par === '-1' ? '#fb7185' : '#fbbf24' }}>{g.Signo_par}</td>
                        <td style={{ padding: '9px', fontFamily: 'monospace', fontWeight: 'bold', color: Number(g.Contribucion) > 0 ? '#34d399' : Number(g.Contribucion) < 0 ? '#f87171' : '#64748b' }}>
                          {Number(g.Contribucion) > 0 ? `+${Number(g.Contribucion)}` : Number(g.Contribucion)}
                        </td>
                        <td style={{ padding: '9px', fontSize: '11px', color: '#cbd5e1' }}>{g.Estado_par}</td>
                        <td style={{ padding: '9px', fontFamily: 'monospace', fontSize: '11px', color: '#94a3b8' }}>{g.Origen}</td>
                        <td style={{ padding: '9px', color: '#cbd5e1', maxWidth: '380px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }} title={[g.Motivos, g.Votos].filter(Boolean).join(' | ')}>
                          {[g.Votos, g.Motivos].filter(Boolean).join(' · ')}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {resultado && (
                <div style={{ marginTop: '12px', fontSize: '11px', color: '#64748b' }}>
                  LLM: {resultado.llm.llamadas} llamadas, {resultado.llm.reutilizadas} respuestas reutilizadas, {resultado.llm.tokens.toLocaleString('es-ES')} tokens. Ficheros de las tres fases en <code>{resultado.carpeta}</code>.
                </div>
              )}
            </>
          )}
        </section>
      </main>

      {/* CONFIRMACIÓN ANTES DE EJECUTAR */}
      {confirmando && rutaSel && (
        <div style={{ position: 'fixed', inset: 0, backgroundColor: 'rgba(2, 6, 23, 0.8)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '16px', zIndex: 50 }}>
          <div style={{ backgroundColor: '#0f172a', border: '1px solid #334155', borderRadius: '14px', padding: '22px', maxWidth: '520px', width: '100%' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
              <h3 style={{ margin: 0, fontSize: '16px', fontWeight: 'bold', color: '#5eead4' }}>¿Ejecutar esta ruta?</h3>
              <button onClick={() => setConfirmando(false)} style={{ background: 'none', border: 'none', color: '#94a3b8', cursor: 'pointer' }}><X size={18} /></button>
            </div>
            <div style={{ fontSize: '13px', color: '#e2e8f0', display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <div><span style={{ fontFamily: 'monospace', color: '#2dd4bf', fontWeight: 'bold' }}>{rutaSel.GO_ID}</span> · {rutaSel.Descripcion}</div>
              <div style={{ fontSize: '12px', color: '#94a3b8' }}>
                {genes(rutaSel.Genes_up).length} genes up · {genes(rutaSel.Genes_down).length} genes down
              </div>
              <div style={{ fontSize: '12px', color: '#94a3b8', lineHeight: 1.5 }}>
                Se ejecutan seguidas las tres fases: ingesta (GO y abstracts de PubMed), inferencia con Gemini (gpt-oss solo si Gemini falla) y Net Pathway Score.
                Con las cachés tarda unos segundos; en frío, unos 2–3 minutos. Las respuestas ya registradas no se vuelven a pedir al LLM.
              </div>
            </div>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '18px' }}>
              <button onClick={() => setConfirmando(false)} style={{ padding: '8px 14px', fontSize: '12px', borderRadius: '8px', border: '1px solid #334155', backgroundColor: '#1e293b', color: '#cbd5e1', cursor: 'pointer' }}>
                Cancelar
              </button>
              <button onClick={ejecutarRuta} style={{ padding: '8px 16px', fontSize: '12px', fontWeight: 'bold', borderRadius: '8px', border: 'none', backgroundColor: '#14b8a6', color: '#020617', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px' }}>
                <Play size={14} />
                <span>Confirmar y ejecutar</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
