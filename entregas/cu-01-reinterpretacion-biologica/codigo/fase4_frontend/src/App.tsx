import React, { useState, useMemo, useEffect, useRef } from 'react';
import {
  UploadCloud,
  FileSpreadsheet,
  Search,
  Info,
  Microscope,
  Circle,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
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

// Una ruta GO de CIMUS: puede estar en las dos listas (sobreexpresadas y infraexpresadas)
interface Ruta {
  GO_ID: string;
  Descripcion: string;
  Genes_up: string;
  Genes_down: string;
}

interface GeneContribution {
  Gen: string;
  GO_ID: string;
  Direccion: string;
  Signo_par: string;
  Estado_par: string;
  Motivos: string | null;
  Origen: string;
  W_pos: number | null;
  W_neg: number | null;
  Contribucion: number;
}

interface PathwayResult {
  GO_ID: string;
  Ruta_Nombre: string;
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

interface Articulo {
  PMID: string;
  Titulo: string;
  Signo: string;
  Estado: string;
  Motivos: string;
  Confianza: number | null;
  Cita: string;
  Votos: Voto[];
}

// Un voto del artículo: uno por cada subproceso de la ruta por el que se preguntó al LLM
interface Voto {
  Proceso: string;
  Signo: string;
  Organismo: string;
  Tipo_celular: string;
  Confianza: number | null;
  Peso: number;
}

interface DetalleGen {
  articulos: Articulo[];
  GO?: { Evidencias: string; PMIDs: string[]; Motivo: string };
}

interface Resultado {
  rutas: PathwayResult[];
  pares: GeneContribution[];
  genes: Record<string, DetalleGen>;
  resumen: {
    fase1: { genes: number; inmunoglobulinas: number; signo_GO: number; genes_con_articulos: number; articulos: number; sin_articulos: number };
    fase2: { articulos_leidos: number; no_mencionan_gen: number; con_signo: number; sin_conclusion: number };
  };
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

// Umbrales de lectura de la Fase 3 (fase3_scoring/config.py)
const UMBRAL_NPS = 0.33;
const MIN_PARES_CON_SIGNO = 3;
const MIN_COBERTURA = 0.3;

// Los códigos de las fases, dichos en lenguaje llano
const SIGNO_TEXTO: Record<string, string> = {
  '+1': 'Activa el proceso',
  '-1': 'Inhibe el proceso',
  neutro: 'No lo cambia',
  UNKNOWN: 'Sin conclusión',
};

const MOTIVO_TEXTO: Record<string, string> = {
  aceptado_por_GO: 'Gene Ontology lo anota con evidencia experimental; no hace falta el LLM.',
  evidencia_debil: 'Evidencia débil: pocos artículos o poca confianza (suelen ser un solo artículo).',
  inmunoglobulina: 'Es una inmunoglobulina: se cuenta como neutra.',
  sin_evidencia: 'No se encontró ningún artículo sobre el gen en este proceso.',
  no_menciona_gen: 'Los artículos encontrados no nombran el gen, así que no se preguntó al LLM.',
  baja_confianza: 'El LLM no estaba lo bastante seguro.',
  marcador_correlacion: 'El artículo solo usa el gen como marcador o muestra una correlación, no un efecto.',
  contexto_ajeno: 'El artículo trata de otro proceso.',
  direccion_inversa: 'En el artículo el gen es el que recibe el efecto, no el que lo causa.',
  efecto_indirecto: 'El efecto es de otra molécula, no del gen.',
  especulativo: 'El artículo solo lo plantea como hipótesis.',
  contradictorio: 'El artículo da resultados contradictorios.',
  cita_no_verificada: 'La frase que citó el LLM no está en el abstract: se descarta.',
  conflicto_entre_abstracts: 'Unos artículos dicen que activa y otros que inhibe: hay que revisarlo a mano.',
  minoria_discrepante: 'Algún artículo dice lo contrario que la mayoría.',
  discrepancia_polaridad_GO: 'El LLM y Gene Ontology no coinciden.',
  coincide_polaridad_GO: 'El LLM coincide con Gene Ontology.',
  respaldo_secundario: 'Respondió gpt-oss porque Gemini falló.',
  peso_por_defecto: 'Sin confianza del modelo: se usó un peso por defecto.',
  votos_sin_peso: 'Los artículos no pesan lo suficiente.',
  incoherencia_respuesta: 'La respuesta del LLM era incoherente.',
  json_invalido: 'La respuesta del LLM no se pudo leer.',
  LLM_y_revision: 'Gen con función doble conocida: se revisa siempre.',
};

const motivos = (m: string | null | undefined) =>
  (m || '').split('|').map((x) => x.trim()).filter(Boolean).map((x) => MOTIVO_TEXTO[x] || x);

// Peso de cada voto en la Fase 3 (fase3_scoring/config.py): confianza / 100, por 0,5 si el estudio no es en humano
// y otro 0,5 si no es en células inmunes. Un gen con menos de MIN_PESO_EVIDENCIA a su favor tiene evidencia débil.
const MIN_PESO_EVIDENCIA = 1;
const ORGANISMOS_VALIDOS = ['human', 'not_stated', ''];
const TIPOS_CELULARES_VALIDOS = ['NK', 'T', 'other_immune', 'not_stated', ''];
const ORGANISMO_TEXTO: Record<string, string> = { mouse: 'ratón', rat: 'rata', other: 'otro organismo' };
const CELULA_TEXTO: Record<string, string> = { tumor: 'células tumorales', other: 'células no inmunes' };

const coma = (v: number) => v.toFixed(2).replace('.', ',');

const calculoPeso = (v: Voto) => {
  const factores: string[] = [];
  if (!ORGANISMOS_VALIDOS.includes(v.Organismo)) factores.push(`0,5 por ser en ${ORGANISMO_TEXTO[v.Organismo] || v.Organismo}`);
  if (!TIPOS_CELULARES_VALIDOS.includes(v.Tipo_celular)) factores.push(`0,5 por ser en ${CELULA_TEXTO[v.Tipo_celular] || v.Tipo_celular}`);
  const confianza = v.Confianza === null ? 'confianza por defecto 50 %' : `confianza ${v.Confianza} %`;
  return factores.length ? `${coma(v.Peso)} (${confianza} × ${factores.join(' × ')})` : `${coma(v.Peso)} (${confianza})`;
};

const PesoEvidencia = ({ g }: { g: GeneContribution }) => {
  if (g.Origen !== 'LLM') return <span style={{ color: '#475569' }}>—</span>;
  const pos = Number(g.W_pos || 0);
  const neg = Number(g.W_neg || 0);
  const debil = Math.max(pos, neg) < MIN_PESO_EVIDENCIA;
  const barra = (w: number, color: string) => (
    <div style={{ width: `${Math.min(w / 2, 1) * 100}%`, height: '100%', backgroundColor: color }} />
  );
  return (
    <div style={{ minWidth: '120px' }}>
      <div style={{ position: 'relative', width: '120px', height: '6px', backgroundColor: '#1e293b', borderRadius: '3px', overflow: 'hidden', display: 'flex' }}>
        {pos > 0 && barra(pos, '#2dd4bf')}
        {neg > 0 && barra(neg, '#fb7185')}
        <div title="Umbral: peso 1" style={{ position: 'absolute', left: '50%', top: 0, bottom: 0, width: '2px', backgroundColor: '#f8fafc' }} />
      </div>
      <div style={{ fontSize: '11px', color: debil ? '#fbbf24' : '#cbd5e1', marginTop: '3px' }}>
        {pos > 0 && <>{coma(pos)} activa</>}
        {pos > 0 && neg > 0 && ' · '}
        {neg > 0 && <>{coma(neg)} inhibe</>}
        {debil && ' (débil, < 1)'}
      </div>
    </div>
  );
};

const efectoTexto = (c: number) => (c > 0 ? 'Empuja hacia activada' : c < 0 ? 'Empuja hacia inhibida' : 'No cuenta');

const fuenteTexto = (g: GeneContribution, d?: DetalleGen) => {
  if (g.Origen === 'GO') return 'Gene Ontology';
  if (g.Origen === 'Ig') return 'Inmunoglobulina';
  const n = d?.articulos.length || 0;
  return n ? `${n} artículo${n > 1 ? 's' : ''}` : '—';
};

const PASOS = [
  { step: 1, title: 'Fase 1 · Ingesta GO & PubMed', desc: 'Subárbol GO, triaje y descarga de abstracts' },
  { step: 2, title: 'Fase 2 · Inferencia LLM', desc: 'Gemini, con gpt-oss solo de respaldo; citas verificadas' },
  { step: 3, title: 'Fase 3 · Scoring NPS', desc: 'Signo de cada gen y Net Pathway Score' },
];

const tarjeta: React.CSSProperties = { backgroundColor: '#020617', border: '1px solid #1e293b', borderRadius: '12px', padding: '14px', display: 'flex', flexDirection: 'column', gap: '6px' };
const tituloTarjeta: React.CSSProperties = { fontSize: '12px', fontWeight: 'bold', color: '#5eead4' };
const lineaTarjeta: React.CSSProperties = { fontSize: '12px', color: '#cbd5e1', lineHeight: 1.5 };

export default function App() {
  const [backendOnline, setBackendOnline] = useState<boolean>(false);

  const [rutas, setRutas] = useState<Ruta[]>([]);
  const [origenRutas, setOrigenRutas] = useState<string>('');
  const [search, setSearch] = useState('');
  const [seleccion, setSeleccion] = useState<string | null>(null);
  const [confirmando, setConfirmando] = useState(false);

  const [isRunning, setIsRunning] = useState(false);
  const [currentStep, setCurrentStep] = useState<number>(0);
  const [segundos, setSegundos] = useState<number>(0);
  const [feedback, setFeedback] = useState<{ type: 'info' | 'ok' | 'err'; msg: string } | null>(null);
  const [resultado, setResultado] = useState<Resultado | null>(null);
  const [abierto, setAbierto] = useState<string | null>(null);
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
          setAbierto(null);
          setCurrentStep(4);
          setIsRunning(false);
          const pend = r.llm.pendientes
            ? ` ⚠️ ${r.llm.pendientes} preguntas quedaron pendientes (cupo del LLM agotado): vuelve a ejecutar la ruta más tarde.`
            : '';
          setFeedback({ type: 'ok', msg: `${d.GO_ID} ejecutada en ${r.tiempos.fase1 + r.tiempos.fase2 + r.tiempos.fase3} s.${pend}` });
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

  // Excel de CIMUS (ID, Description, geneID) de una de las dos listas: sustituye los genes de esa lista
  const handleExcelUpload = async (e: React.ChangeEvent<HTMLInputElement>, campo: 'Genes_up' | 'Genes_down') => {
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
      const base: Record<string, Ruta> = {};
      rutas.forEach((r) => (base[r.GO_ID] = { ...r, [campo]: '' }));
      rows.forEach((r) => {
        const id = String(r.ID || '').trim();
        if (!id) return;
        base[id] = base[id] || { GO_ID: id, Descripcion: String(r.Description || '').trim(), Genes_up: '', Genes_down: '' };
        base[id][campo] = String(r.geneID || '').trim();
      });
      setRutas(Object.values(base).filter((r) => r.Genes_up || r.Genes_down).sort((a, b) => a.GO_ID.localeCompare(b.GO_ID)));
      const lista = campo === 'Genes_up' ? 'rutas sobreexpresadas (upregulated)' : 'rutas infraexpresadas (downregulated)';
      setOrigenRutas((prev) => `${prev} · ${lista}: ${file.name}`);
      setSeleccion(null);
      setFeedback({ type: 'ok', msg: `${rows.length} ${lista} leídas de ${file.name}. Elige una ruta y ejecútala.` });
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

  const botonSubir: React.CSSProperties = { padding: '7px 14px', borderRadius: '8px', border: '1px solid #334155', backgroundColor: '#1e293b', color: '#f8fafc', fontSize: '12px', fontWeight: 500, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px' };

  // Explicación del NPS con los números de la ruta
  const explicacionNPS = (r: PathwayResult) => {
    const conSigno = r.n_activan + r.n_inhiben;
    if (conSigno < MIN_PARES_CON_SIGNO || r.Cobertura < MIN_COBERTURA) {
      return `Solo ${conSigno} genes tienen signo (cobertura ${(r.Cobertura * 100).toFixed(0)} %): hacen falta al menos ${MIN_PARES_CON_SIGNO} y una cobertura del ${MIN_COBERTURA * 100} % para leer la ruta.`;
    }
    const regla = r.Lectura === 'activada' ? `≥ +${UMBRAL_NPS}` : r.Lectura === 'inhibida' ? `≤ −${UMBRAL_NPS}` : `entre −${UMBRAL_NPS} y +${UMBRAL_NPS}`;
    return `NPS = (${r.n_activan} − ${r.n_inhiben}) / ${conSigno} = ${formatoNPS(r.NPS)}, ${regla} → ${r.Lectura}.`;
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
                <span>Elige la ruta que quieres ejecutar</span>
              </h2>
              <p style={{ margin: 0, fontSize: '12px', color: '#94a3b8' }}>
                Marca una ruta y confirma: se ejecutan seguidas las Fases 1, 2 y 3 con sus genes sobreexpresados e infraexpresados.
                {origenRutas && <> Rutas de: <strong style={{ color: '#cbd5e1' }}>{origenRutas}</strong>.</>}
              </p>
            </div>

            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', alignItems: 'center' }}>
              <label style={botonSubir} title="Excel de CIMUS con las rutas sobreexpresadas, upregulated (columnas ID, Description y geneID)">
                <input type="file" accept=".xlsx,.xls,.csv" onChange={(e) => handleExcelUpload(e, 'Genes_up')} style={{ display: 'none' }} />
                <UploadCloud size={15} color="#6ee7b7" />
                <span>Subir rutas sobreexpresadas (upregulated)</span>
              </label>

              <label style={botonSubir} title="Excel de CIMUS con las rutas infraexpresadas, downregulated (columnas ID, Description y geneID)">
                <input type="file" accept=".xlsx,.xls,.csv" onChange={(e) => handleExcelUpload(e, 'Genes_down')} style={{ display: 'none' }} />
                <UploadCloud size={15} color="#fda4af" />
                <span>Subir rutas infraexpresadas (downregulated)</span>
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
                  <th style={{ padding: '8px 10px' }}>Genes sobreexpresados (up)</th>
                  <th style={{ padding: '8px 10px' }}>Genes infraexpresados (down)</th>
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

        {/* RESULTADO DE LA RUTA: UNA TARJETA POR FASE Y EL DESGLOSE POR GEN */}
        <section style={{ backgroundColor: '#0f172a', border: '1px solid #1e293b', borderRadius: '16px', padding: '18px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {!rutaRes || !resultado ? (
            <div style={{ color: '#64748b', fontSize: '13px', padding: '20px', textAlign: 'center' }}>
              {isRunning ? 'Ejecutando la ruta: el resultado aparecerá aquí al terminar la Fase 3.' : 'Aún no se ha ejecutado ninguna ruta.'}
            </div>
          ) : (
            <>
              <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'space-between', alignItems: 'center', gap: '12px' }}>
                <div>
                  <span style={{ fontFamily: 'monospace', fontSize: '12px', color: '#2dd4bf', fontWeight: 'bold' }}>{rutaRes.GO_ID}</span>
                  <h3 style={{ margin: '2px 0 0 0', fontSize: '16px', fontWeight: 'bold' }}>Resultado · {rutaRes.Ruta_Nombre}</h3>
                </div>
                <button
                  onClick={() => descargarBase64Excel(resultado.excel_b64, resultado.nombre_excel)}
                  style={{ padding: '6px 12px', fontSize: '11px', borderRadius: '6px', border: 'none', backgroundColor: '#14b8a6', color: '#020617', fontWeight: 'bold', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '5px' }}
                >
                  <Download size={13} />
                  <span>Descargar Excel de la Fase 3</span>
                </button>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '12px' }}>
                <div style={tarjeta}>
                  <span style={tituloTarjeta}>Fase 1 · Qué se encontró</span>
                  <span style={lineaTarjeta}>{resultado.resumen.fase1.genes} genes en la ruta.</span>
                  <span style={lineaTarjeta}>
                    {resultado.resumen.fase1.signo_GO} con signo directo de Gene Ontology
                    {resultado.resumen.fase1.inmunoglobulinas > 0 && <>, {resultado.resumen.fase1.inmunoglobulinas} inmunoglobulina{resultado.resumen.fase1.inmunoglobulinas > 1 ? 's' : ''} (neutras)</>}.
                  </span>
                  <span style={lineaTarjeta}>
                    {resultado.resumen.fase1.articulos} artículos de PubMed para {resultado.resumen.fase1.genes_con_articulos} genes
                    {resultado.resumen.fase1.sin_articulos > 0 && <>; {resultado.resumen.fase1.sin_articulos} sin ningún artículo</>}.
                  </span>
                </div>

                <div style={tarjeta}>
                  <span style={tituloTarjeta}>Fase 2 · Qué dicen los artículos</span>
                  <span style={lineaTarjeta}>
                    El LLM leyó {resultado.resumen.fase2.articulos_leidos} artículos: {resultado.resumen.fase2.con_signo} dicen si el gen activa o inhibe el proceso
                    {resultado.resumen.fase2.sin_conclusion > 0 && <> y {resultado.resumen.fase2.sin_conclusion} no permiten concluir</>}.
                  </span>
                  {resultado.resumen.fase2.no_mencionan_gen > 0 && (
                    <span style={lineaTarjeta}>{resultado.resumen.fase2.no_mencionan_gen} artículos no nombraban el gen y no se le preguntaron.</span>
                  )}
                  <span style={{ ...lineaTarjeta, color: '#64748b' }}>
                    {resultado.llm.llamadas} llamadas nuevas al LLM ({resultado.llm.tokens.toLocaleString('es-ES')} tokens) y {resultado.llm.reutilizadas} respuestas ya guardadas.
                  </span>
                </div>

                <div style={{ ...tarjeta, borderColor: colorLectura(rutaRes.Lectura) }}>
                  <span style={tituloTarjeta}>Fase 3 · Lectura de la ruta</span>
                  <span style={{ fontSize: '20px', fontWeight: 'bold', textTransform: 'uppercase', color: colorLectura(rutaRes.Lectura) }}>
                    {rutaRes.Lectura} <span style={{ fontSize: '14px' }}>(NPS {formatoNPS(rutaRes.NPS)})</span>
                  </span>
                  <span style={lineaTarjeta}>
                    {rutaRes.n_activan} genes empujan hacia activada, {rutaRes.n_inhiben} hacia inhibida y {rutaRes.n_total - rutaRes.n_activan - rutaRes.n_inhiben} no cuentan.
                  </span>
                  <span style={lineaTarjeta}>{explicacionNPS(rutaRes)}</span>
                  <span style={{ ...lineaTarjeta, color: '#64748b' }}>
                    Pesando cada gen por su log2FC: NPS {formatoNPS(rutaRes.NPS_log2FC)} ({rutaRes.Lectura_log2FC || 'sin tabla'}).
                    {rutaRes.Sensible_al_peso === 'sí' && <strong style={{ color: '#fbbf24' }}> La lectura cambia con ese peso: revisarla.</strong>}
                    {rutaRes.n_pendiente > 0 && <strong style={{ color: '#fbbf24' }}> {rutaRes.n_pendiente} genes pendientes de la Fase 2.</strong>}
                  </span>
                </div>
              </div>

              <div style={{ fontSize: '12px', color: '#94a3b8' }}>
                Un gen empuja hacia <strong>activada</strong> si activa el proceso y está sobreexpresado en NK, o si lo inhibe y está infraexpresado; hacia <strong>inhibida</strong> en los otros dos casos.
                El <strong>peso</strong> de cada artículo es la confianza del LLM, por 0,5 si el estudio no es en humano y otro 0,5 si no es en células inmunes; un gen con un peso total menor que 1 (la raya blanca de la barra) tiene evidencia débil.
                Pulsa un gen para ver sus artículos y el cálculo.
              </div>

              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px', textAlign: 'left' }}>
                  <thead style={{ backgroundColor: '#020617' }}>
                    <tr style={{ borderBottom: '1px solid #1e293b', color: '#94a3b8' }}>
                      <th style={{ padding: '9px', width: '20px' }}></th>
                      <th style={{ padding: '9px' }}>Gen</th>
                      <th style={{ padding: '9px' }}>En NK</th>
                      <th style={{ padding: '9px' }}>Qué hace en el proceso</th>
                      <th style={{ padding: '9px' }}>Efecto en la ruta</th>
                      <th style={{ padding: '9px' }}>Fuente</th>
                      <th style={{ padding: '9px' }}>Peso de la evidencia</th>
                      <th style={{ padding: '9px' }}>Por qué</th>
                    </tr>
                  </thead>
                  <tbody>
                    {paresRes.map((g) => {
                      const d = resultado.genes[g.Gen];
                      const c = Number(g.Contribucion);
                      const abiertoGen = abierto === g.Gen;
                      return (
                        <React.Fragment key={g.Gen}>
                          <tr onClick={() => setAbierto(abiertoGen ? null : g.Gen)} style={{ borderBottom: '1px solid rgba(30, 41, 59, 0.5)', cursor: 'pointer', backgroundColor: abiertoGen ? 'rgba(20, 184, 166, 0.06)' : 'transparent' }}>
                            <td style={{ padding: '9px', color: '#64748b' }}>{abiertoGen ? <ChevronDown size={14} /> : <ChevronRight size={14} />}</td>
                            <td style={{ padding: '9px', fontFamily: 'monospace', fontWeight: 'bold' }}>{g.Gen}</td>
                            <td style={{ padding: '9px', color: g.Direccion === 'up' ? '#6ee7b7' : '#fda4af' }}>{g.Direccion === 'up' ? 'Sobreexpresado' : 'Infraexpresado'}</td>
                            <td style={{ padding: '9px', fontWeight: 'bold', color: g.Signo_par === '+1' ? '#2dd4bf' : g.Signo_par === '-1' ? '#fb7185' : '#fbbf24' }}>
                              {SIGNO_TEXTO[g.Signo_par] || g.Signo_par}
                              {g.Estado_par === 'revisar' && <span style={{ fontWeight: 'normal', color: '#fbbf24' }}> (a revisar)</span>}
                              {g.Estado_par === 'pendiente' && <span style={{ fontWeight: 'normal', color: '#fbbf24' }}> (pendiente)</span>}
                            </td>
                            <td style={{ padding: '9px', fontWeight: 'bold', color: c > 0 ? '#34d399' : c < 0 ? '#f87171' : '#64748b' }}>{efectoTexto(c)}</td>
                            <td style={{ padding: '9px', color: '#94a3b8' }}>{fuenteTexto(g, d)}</td>
                            <td style={{ padding: '9px' }}><PesoEvidencia g={g} /></td>
                            <td style={{ padding: '9px', color: '#cbd5e1' }}>{motivos(g.Motivos).join(' ') || (g.Origen === 'LLM' ? 'Los artículos coinciden.' : '')}</td>
                          </tr>
                          {abiertoGen && (
                            <tr style={{ borderBottom: '1px solid rgba(30, 41, 59, 0.5)' }}>
                              <td></td>
                              <td colSpan={7} style={{ padding: '4px 9px 14px 9px' }}>
                                {d?.GO && g.Origen === 'GO' && (
                                  <div style={{ fontSize: '12px', color: '#cbd5e1', marginBottom: '8px' }}>
                                    Anotación curada de Gene Ontology (evidencia {d.GO.Evidencias || '—'})
                                    {d.GO.PMIDs.length > 0 && <>: {d.GO.PMIDs.map((p, i) => <React.Fragment key={p}>{i > 0 && ', '}<a href={`https://pubmed.ncbi.nlm.nih.gov/${p}/`} target="_blank" rel="noreferrer" style={{ color: '#38bdf8' }}>PMID {p}</a></React.Fragment>)}</>}.
                                  </div>
                                )}
                                {(d?.articulos || []).map((a) => (
                                  <div key={a.PMID} style={{ borderLeft: `3px solid ${a.Signo === '+1' ? '#2dd4bf' : a.Signo === '-1' ? '#fb7185' : '#475569'}`, padding: '6px 10px', marginBottom: '8px', backgroundColor: '#020617', borderRadius: '6px' }}>
                                    <div style={{ fontSize: '12px' }}>
                                      <a href={`https://pubmed.ncbi.nlm.nih.gov/${a.PMID}/`} target="_blank" rel="noreferrer" style={{ color: '#38bdf8' }}>PMID {a.PMID}</a>
                                      {a.Titulo && <span style={{ color: '#e2e8f0' }}> · {a.Titulo}</span>}
                                    </div>
                                    <div style={{ fontSize: '12px', color: '#94a3b8', marginTop: '3px' }}>
                                      <strong style={{ color: a.Signo === '+1' ? '#2dd4bf' : a.Signo === '-1' ? '#fb7185' : '#fbbf24' }}>{SIGNO_TEXTO[a.Signo] || a.Signo}</strong>
                                      {motivos(a.Motivos).length > 0 && <> · {motivos(a.Motivos).join(' ')}</>}
                                    </div>
                                    {a.Votos.length > 0 && (
                                      <div style={{ fontSize: '12px', color: '#94a3b8', marginTop: '4px' }}>
                                        {a.Votos.length > 1 ? `Cuenta ${a.Votos.length} veces, una por cada subproceso de la ruta por el que se preguntó:` : 'Cuenta una vez:'}
                                        <ul style={{ margin: '2px 0 0 0', paddingLeft: '18px' }}>
                                          {a.Votos.map((v, i) => (
                                            <li key={i}>
                                              {v.Proceso}: <strong style={{ color: v.Signo === '+1' ? '#2dd4bf' : v.Signo === '-1' ? '#fb7185' : '#fbbf24' }}>{(SIGNO_TEXTO[v.Signo] || v.Signo).toLowerCase()}</strong>
                                              {['+1', '-1', 'neutro'].includes(v.Signo) && <>, peso {calculoPeso(v)}</>}
                                            </li>
                                          ))}
                                        </ul>
                                      </div>
                                    )}
                                    {a.Cita && <div style={{ fontSize: '12px', color: '#cbd5e1', fontStyle: 'italic', marginTop: '4px' }}>«{a.Cita}»</div>}
                                  </div>
                                ))}
                                {!d?.articulos.length && g.Origen !== 'GO' && <div style={{ fontSize: '12px', color: '#64748b' }}>Sin artículos que mostrar.</div>}
                                {g.Origen === 'LLM' && (
                                  <div style={{ fontSize: '12px', color: '#cbd5e1' }}>
                                    Peso total: {coma(Number(g.W_pos || 0))} a favor de que activa y {coma(Number(g.W_neg || 0))} a favor de que inhibe.
                                    {Math.max(Number(g.W_pos || 0), Number(g.W_neg || 0)) < MIN_PESO_EVIDENCIA && ' No llega a 1: la evidencia es débil, pero el signo cuenta igual en el NPS.'}
                                  </div>
                                )}
                              </td>
                            </tr>
                          )}
                        </React.Fragment>
                      );
                    })}
                  </tbody>
                </table>
              </div>
              <div style={{ fontSize: '11px', color: '#64748b' }}>
                Ficheros de las tres fases en <code>{resultado.carpeta}</code>.
              </div>
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
                {genes(rutaSel.Genes_up).length} sobreexpresados · {genes(rutaSel.Genes_down).length} infraexpresados
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
