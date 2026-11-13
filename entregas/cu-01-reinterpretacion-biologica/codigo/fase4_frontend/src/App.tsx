import React, { useState, useMemo, useEffect } from 'react';
import {
  Dna,
  UploadCloud,
  FileSpreadsheet,
  Search,
  Info,
  Microscope,
  CheckSquare,
  Square,
  Download,
  Play,
  Loader2,
  CheckCircle2,
  HelpCircle,
  X
} from 'lucide-react';

const API_URL = 'http://127.0.0.1:8000';

const loadXLSX = (): Promise<any> => {
  return new Promise((resolve, reject) => {
    if ((window as any).XLSX) {
      resolve((window as any).XLSX);
      return;
    }
    const script = document.createElement('script');
    script.src = 'https://cdn.jsdelivr.net/npm/xlsx@0.18.5/dist/xlsx.full.min.js';
    script.onload = () => resolve((window as any).XLSX);
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

const archivoABase64 = (file: File): Promise<string> => {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const res = reader.result as string;
      resolve(res.split(',')[1]);
    };
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
};

interface RawRouteRow {
  rowId: string;
  go_id: string;
  description: string;
  geneID: string;
  genesList: string[];
  lista: 'Activada' | 'Suprimida';
  selected: boolean;
}

interface GeneContribution {
  Gen: string;
  GO_ID: string;
  Ruta_Nombre: string;
  Direccion: string;
  Signo_par: string;
  Estado_par: string;
  Motivos: string;
  Origen: string;
  Votos: string;
  Contribucion: number;
  Freno_retroalimentacion: boolean;
}

interface PathwayResult {
  GO_ID: string;
  Ruta_Nombre: string;
  Listas: string;
  NPS: number | null;
  Lectura: string;
  Sensible_al_peso?: string;
  n_total: number;
  n_activan: number;
  n_inhiben: number;
  Cobertura: number;
}

interface PhaseRunResult {
  resumen: string;
  preview: any[];
  excel_b64: string;
  nombre_excel: string;
}

const DEMO_RAW: RawRouteRow[] = [
  {
    rowId: '1',
    go_id: 'GO:0002443',
    description: 'leukocyte mediated immunity',
    geneID: 'CD7/PRF1/GZMB/TGFB1/IGKC/KLRD1/NKG7',
    genesList: ['CD7', 'PRF1', 'GZMB', 'TGFB1', 'IGKC', 'KLRD1', 'NKG7'],
    lista: 'Activada',
    selected: true,
  },
  {
    rowId: '2',
    go_id: 'GO:0001912',
    description: 'positive regulation of leukocyte mediated cytotoxicity',
    geneID: 'KLRC1/FCGR3A/NCAM1/IFNG',
    genesList: ['KLRC1', 'FCGR3A', 'NCAM1', 'IFNG'],
    lista: 'Suprimida',
    selected: true,
  },
  {
    rowId: '3',
    go_id: 'GO:0042110',
    description: 'T cell activation',
    geneID: 'IL2RB/CD28/LCK/ZAP70/CTLA4/PDCD1',
    genesList: ['IL2RB', 'CD28', 'LCK', 'ZAP70', 'CTLA4', 'PDCD1'],
    lista: 'Activada',
    selected: false,
  },
];

const DEMO_RUTAS_RES: PathwayResult[] = [
  {
    GO_ID: 'GO:0002443',
    Ruta_Nombre: 'leukocyte mediated immunity',
    Listas: 'ambas',
    NPS: 0.38,
    Lectura: 'activada',
    Sensible_al_peso: 'no',
    n_total: 7,
    n_activan: 4,
    n_inhiben: 1,
    Cobertura: 0.86,
  },
  {
    GO_ID: 'GO:0001912',
    Ruta_Nombre: 'positive regulation of leukocyte mediated cytotoxicity',
    Listas: 'ambas',
    NPS: -0.45,
    Lectura: 'inhibida',
    Sensible_al_peso: 'sí',
    n_total: 4,
    n_activan: 1,
    n_inhiben: 3,
    Cobertura: 1.0,
  },
];

const DEMO_PARES_RES: GeneContribution[] = [
  { Gen: 'PRF1', GO_ID: 'GO:0002443', Ruta_Nombre: 'leukocyte mediated immunity', Direccion: 'up', Signo_par: '+1', Estado_par: 'resuelto', Motivos: 'aceptado_por_GO', Origen: 'GO', Votos: 'GAF experimental (prof. 1)', Contribucion: 1, Freno_retroalimentacion: false },
  { Gen: 'GZMB', GO_ID: 'GO:0002443', Ruta_Nombre: 'leukocyte mediated immunity', Direccion: 'up', Signo_par: '+1', Estado_par: 'resuelto', Motivos: 'veredicto_validado', Origen: 'LLM', Votos: '+1:28456102(0.92)', Contribucion: 1, Freno_retroalimentacion: false },
  { Gen: 'TGFB1', GO_ID: 'GO:0002443', Ruta_Nombre: 'leukocyte mediated immunity', Direccion: 'up', Signo_par: '-1', Estado_par: 'resuelto', Motivos: 'freno_retroalimentacion', Origen: 'LLM', Votos: '-1:31092833(0.88)', Contribucion: -1, Freno_retroalimentacion: true },
  { Gen: 'CD7', GO_ID: 'GO:0002443', Ruta_Nombre: 'leukocyte mediated immunity', Direccion: 'up', Signo_par: 'UNKNOWN', Estado_par: 'revisar', Motivos: 'baja_confianza | discrepancia_polaridad_GO', Origen: 'LLM', Votos: 'PMID 10652336 (efecto de K12-Fc)', Contribucion: 0, Freno_retroalimentacion: false },
  { Gen: 'IGKC', GO_ID: 'GO:0002443', Ruta_Nombre: 'leukocyte mediated immunity', Direccion: 'up', Signo_par: 'neutro', Estado_par: 'resuelto', Motivos: 'inmunoglobulina', Origen: 'Ig', Votos: 'HGNC immunoglobulin gene', Contribucion: 0, Freno_retroalimentacion: false },
  { Gen: 'KLRC1', GO_ID: 'GO:0001912', Ruta_Nombre: 'positive regulation of leukocyte mediated cytotoxicity', Direccion: 'up', Signo_par: '-1', Estado_par: 'resuelto', Motivos: 'freno_retroalimentacion | respaldo_secundario', Origen: 'LLM', Votos: '-1:30987411(0.82)', Contribucion: -1, Freno_retroalimentacion: true },
  { Gen: 'FCGR3A', GO_ID: 'GO:0001912', Ruta_Nombre: 'positive regulation of leukocyte mediated cytotoxicity', Direccion: 'down', Signo_par: '+1', Estado_par: 'resuelto', Motivos: 'aceptado_por_GO', Origen: 'GO', Votos: 'GAF experimental', Contribucion: -1, Freno_retroalimentacion: false },
];

const INFO_FASES = {
  f1: {
    titulo: 'Fase 1 · Ingesta de Evidencias GO y Descarga de Abstracts',
    entrada: 'Uno o dos ficheros Excel/CSV de enriquecimiento funcional de CIMUS (rutas de genes up/Activadas y/o down/Suprimidas).',
    columnas: ['ID (identificador de ruta Gene Ontology, ej. GO:0002443)', 'Description (nombre del proceso biológico)', 'geneID (símbolos oficiales HGNC separados por barra "/", ej. CD7/PRF1/GZMB)'],
    proceso: 'Descarga/lee go-basic.obo y goa_human.gaf.gz, aparta inmunoglobulinas (HGNC), propaga cada ruta a todo su subárbol GO, realiza el triaje de polaridad curada (aceptar_GO vs LLM) y recupera títulos y abstracts desde Europe PMC y NCBI.',
    salida: 'Excel "fase1_dataset_abstracts.xlsx" con 7 hojas: Con_abstract, Triaje_polaridad, Inmunoglobulinas, Sin_evidencia, PMID_sin_abstract, Anotado_sin_PMID y Genes_no_encontrados.',
  },
  f2: {
    titulo: 'Fase 2 · Inferencia Mecanística con LLM y Control de Alucinaciones',
    entrada: 'El Excel generado por la Fase 1 ("fase1_dataset_abstracts.xlsx").',
    columnas: ['Hoja "Con_abstract" con Gen, GO_ID, Ruta_Nombre, PMID, Titulo, Abstract, Destino y Polaridad_GO'],
    proceso: 'Limpia el HTML de los abstracts sin alterar nomenclatura biomédica, filtra los que no mencionan el gen, agrupa preguntas por gen y consulta a Gemini 3.5 Flash-Lite (con respaldo de gpt-oss-120b en Groq). Exige cita literal verificada (≥6 palabras) y umbral de confianza ≥80.',
    salida: 'Excel "fase2_resultados.xlsx" con 3 hojas: Por_ruta (signo compuesto y estado por ruta), Preguntas (veredicto, citas verificadas, organismo, tipo celular y motivos) y Resumen.',
  },
  f3: {
    titulo: 'Fase 3 · Agregación de Evidencias y Net Pathway Score (NPS)',
    entrada: 'Dos ficheros obligatorios: salida de Fase 1 ("fase1_dataset_abstracts.xlsx") + salida de Fase 2 ("fase2_resultados.xlsx"). Opcionalmente la tabla de expresión diferencial ("NK_cells_DESeq2_results.xlsx").',
    columnas: ['Fase 1: hojas Triaje_polaridad e Inmunoglobulinas', 'Fase 2: hojas Por_ruta y Preguntas', 'Opcional log2FC: columnas Gen y log2FC / log2FoldChange'],
    proceso: 'Pondera los votos de cada artículo por Confianza_final y contexto biológico (humano y células inmunes), detecta conflictos entre abstracts y calcula NPS = media(signo × dirección) junto con el análisis de sensibilidad por log2FC.',
    salida: 'Excel "fase3_scoring.xlsx" con 4 hojas: Por_ruta (NPS, lectura activada/inhibida/mixta/insuficiente y cobertura), Por_par (aportación de cada gen y frenos), Abstracts_sin_signo y Resumen.',
  },
};

export default function App() {
  const [modo, setModo] = useState<'auto' | 'fases'>('auto');
  const [subFase, setSubFase] = useState<'f1' | 'f2' | 'f3'>('f1');
  const [infoModalKey, setInfoModalKey] = useState<'f1' | 'f2' | 'f3' | null>(null);
  const [backendOnline, setBackendOnline] = useState<boolean>(false);

  // Estado Flujo Completo
  const [rawRows, setRawRows] = useState<RawRouteRow[]>(DEMO_RAW);
  const [defaultLista, setDefaultLista] = useState<'Activada' | 'Suprimida'>('Activada');
  const [searchRaw, setSearchRaw] = useState('');
  const [isRunning, setIsRunning] = useState(false);
  const [currentStep, setCurrentStep] = useState<number>(0);
  const [feedback, setFeedback] = useState<{ type: 'info' | 'ok' | 'err'; msg: string } | null>(null);

  const [rutasRes, setRutasRes] = useState<PathwayResult[]>(DEMO_RUTAS_RES);
  const [paresRes, setParesRes] = useState<GeneContribution[]>(DEMO_PARES_RES);
  const [activeGoId, setActiveGoId] = useState<string>(DEMO_RUTAS_RES[0].GO_ID);
  const [autoExcelDownload, setAutoExcelDownload] = useState<{ b64: string; name: string } | null>(null);

  // Estado Fases Separadas
  const [runningSinglePhase, setRunningSinglePhase] = useState<boolean>(false);
  const [f1SingleRows, setF1SingleRows] = useState<RawRouteRow[]>(DEMO_RAW);
  const [f1SingleLista, setF1SingleLista] = useState<'Activada' | 'Suprimida'>('Activada');
  const [f1SingleResult, setF1SingleResult] = useState<PhaseRunResult | null>(null);

  const [f2InputFile, setF2InputFile] = useState<File | null>(null);
  const [f2SingleResult, setF2SingleResult] = useState<PhaseRunResult | null>(null);

  const [f3InputF1File, setF3InputF1File] = useState<File | null>(null);
  const [f3InputF2File, setF3InputF2File] = useState<File | null>(null);
  const [f3InputLog2File, setF3InputLog2File] = useState<File | null>(null);
  const [f3SingleResult, setF3SingleResult] = useState<PhaseRunResult | null>(null);

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

  const filteredRaw = useMemo(() => {
    return rawRows.filter(
      (r) =>
        r.go_id.toLowerCase().includes(searchRaw.toLowerCase()) ||
        r.description.toLowerCase().includes(searchRaw.toLowerCase()) ||
        r.geneID.toLowerCase().includes(searchRaw.toLowerCase())
    );
  }, [rawRows, searchRaw]);

  const selectedRaw = useMemo(() => rawRows.filter((r) => r.selected), [rawRows]);
  const totalSelectedPairs = useMemo(
    () => selectedRaw.reduce((acc, r) => acc + r.genesList.length, 0),
    [selectedRaw]
  );

  const activePathway = useMemo(
    () => rutasRes.find((r) => r.GO_ID === activeGoId) || rutasRes[0],
    [rutasRes, activeGoId]
  );

  const activeGenes = useMemo(
    () => paresRes.filter((p) => p.GO_ID === activePathway?.GO_ID),
    [paresRes, activePathway]
  );

  // Parseador común de Excel crudo CIMUS
  const parsearExcelCimus = async (file: File, listaDefecto: 'Activada' | 'Suprimida'): Promise<RawRouteRow[]> => {
    const XLSX = await loadXLSX();
    const buffer = await file.arrayBuffer();
    const wb = XLSX.read(buffer, { type: 'array' });
    const sheet = wb.Sheets[wb.SheetNames[0]];
    const rows: any[] = XLSX.utils.sheet_to_json(sheet);

    if (!rows.length || !('ID' in rows[0]) || !('Description' in rows[0]) || !('geneID' in rows[0])) {
      throw new Error('El Excel debe contener las columnas obligatorias: ID, Description y geneID.');
    }

    const listaDetectada: 'Activada' | 'Suprimida' =
      file.name.toLowerCase().includes('suprimid') ? 'Suprimida' : listaDefecto;

    return rows.map((r, i) => {
      const gStr = String(r.geneID || '');
      const gList = gStr.split('/').map((s) => s.trim()).filter(Boolean);
      return {
        rowId: `${Date.now()}_${i}`,
        go_id: String(r.ID || '').trim(),
        description: String(r.Description || '').trim(),
        geneID: gStr,
        genesList: gList,
        lista: listaDetectada,
        selected: i < 5,
      };
    });
  };

  // --- MANEJADORES FLUJO AUTOMÁTICO ---
  const handleAutoExcelUpload = async (e: React.ChangeEvent<HTMLInputElement>, append = false) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const parsed = await parsearExcelCimus(file, defaultLista);
      setRawRows((prev) => (append ? [...prev, ...parsed] : parsed));
      setCurrentStep(0);
      setFeedback({ type: 'ok', msg: `${parsed.length} rutas cargadas (${parsed[0]?.lista}). Selecciona las filas y lanza el pipeline.` });
    } catch (err: any) {
      setFeedback({ type: 'err', msg: err.message });
    }
  };

  const ejecutarPipelineCompleto = async () => {
    if (selectedRaw.length === 0) {
      setFeedback({ type: 'err', msg: 'Selecciona al menos una ruta del Excel antes de ejecutar.' });
      return;
    }
    if (!backendOnline) {
      setFeedback({ type: 'err', msg: 'El motor Python local no está conectado. Ejecuta "python fase4_frontend/api_puente.py" desde codigo/.' });
      return;
    }

    setIsRunning(true);
    setCurrentStep(1);
    setAutoExcelDownload(null);
    setFeedback({ type: 'info', msg: `Ejecutando Fases 1 → 2 → 3 sobre ${selectedRaw.length} rutas (${totalSelectedPairs} pares)...` });

    const activadas = selectedRaw.filter((r) => r.lista === 'Activada').map((r) => ({ ID: r.go_id, Description: r.description, geneID: r.geneID }));
    const suprimidas = selectedRaw.filter((r) => r.lista === 'Suprimida').map((r) => ({ ID: r.go_id, Description: r.description, geneID: r.geneID }));

    try {
      const t1 = setTimeout(() => setCurrentStep(2), 3000);
      const t2 = setTimeout(() => setCurrentStep(3), 7000);

      const res = await fetch(`${API_URL}/ejecutar-todo`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ activadas, suprimidas }),
      });

      clearTimeout(t1);
      clearTimeout(t2);

      const data = await res.json();
      if (!res.ok || !data.ok) throw new Error(data.error || 'Error en pipeline');

      setRutasRes(data.rutas);
      setParesRes(data.pares);
      if (data.rutas.length > 0) setActiveGoId(data.rutas[0].GO_ID);
      if (data.excel_b64) setAutoExcelDownload({ b64: data.excel_b64, name: data.nombre_excel });
      setCurrentStep(4);
      setFeedback({ type: 'ok', msg: `Ejecución completa finalizada: ${data.rutas.length} rutas y ${data.pares.length} pares resueltos.` });
    } catch (err: any) {
      setCurrentStep(0);
      setFeedback({ type: 'err', msg: err.message });
    } finally {
      setIsRunning(false);
    }
  };

  // --- MANEJADORES FASES INDIVIDUALES ---
  const handleF1SingleUpload = async (e: React.ChangeEvent<HTMLInputElement>, append = false) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const parsed = await parsearExcelCimus(file, f1SingleLista);
      setF1SingleRows((prev) => (append ? [...prev, ...parsed] : parsed));
      setF1SingleResult(null);
      setFeedback({ type: 'ok', msg: `Fase 1: ${parsed.length} rutas listas para seleccionar.` });
    } catch (err: any) {
      setFeedback({ type: 'err', msg: err.message });
    }
  };

  const ejecutarFase1Individual = async () => {
    const sel = f1SingleRows.filter((r) => r.selected);
    if (sel.length === 0) {
      setFeedback({ type: 'err', msg: 'Marca al menos una ruta para ejecutar la Fase 1.' });
      return;
    }
    if (!backendOnline) {
      setFeedback({ type: 'err', msg: 'Conecta api_puente.py para ejecutar la Fase 1.' });
      return;
    }

    setRunningSinglePhase(true);
    setFeedback({ type: 'info', msg: `Ejecutando Fase 1 (Ingesta GO y abstracts) para ${sel.length} rutas...` });
    try {
      const activadas = sel.filter((r) => r.lista === 'Activada').map((r) => ({ ID: r.go_id, Description: r.description, geneID: r.geneID }));
      const suprimidas = sel.filter((r) => r.lista === 'Suprimida').map((r) => ({ ID: r.go_id, Description: r.description, geneID: r.geneID }));

      const res = await fetch(`${API_URL}/ejecutar-fase1`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ activadas, suprimidas }),
      });
      const data = await res.json();
      if (!res.ok || !data.ok) throw new Error(data.error || 'Error en Fase 1');

      setF1SingleResult(data);
      setFeedback({ type: 'ok', msg: `Fase 1 completada. ${data.resumen}` });
    } catch (err: any) {
      setFeedback({ type: 'err', msg: err.message });
    } finally {
      setRunningSinglePhase(false);
    }
  };

  const ejecutarFase2Individual = async () => {
    if (!f2InputFile) {
      setFeedback({ type: 'err', msg: 'Sube primero el Excel generado por la Fase 1 (fase1_dataset_abstracts.xlsx).' });
      return;
    }
    if (!backendOnline) {
      setFeedback({ type: 'err', msg: 'Conecta api_puente.py para ejecutar la Fase 2.' });
      return;
    }

    setRunningSinglePhase(true);
    setFeedback({ type: 'info', msg: 'Ejecutando Fase 2 (Inferencia LLM con Gemini 3.5 + respaldo Groq)...' });
    try {
      const b64 = await archivoABase64(f2InputFile);
      const res = await fetch(`${API_URL}/ejecutar-fase2`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ excel_f1_b64: b64 }),
      });
      const data = await res.json();
      if (!res.ok || !data.ok) throw new Error(data.error || 'Error en Fase 2');

      setF2SingleResult(data);
      setFeedback({ type: 'ok', msg: `Fase 2 completada. ${data.resumen}` });
    } catch (err: any) {
      setFeedback({ type: 'err', msg: err.message });
    } finally {
      setRunningSinglePhase(false);
    }
  };

  const ejecutarFase3Individual = async () => {
    if (!f3InputF1File || !f3InputF2File) {
      setFeedback({ type: 'err', msg: 'Sube tanto el Excel de Fase 1 como el Excel de Fase 2 para calcular el scoring.' });
      return;
    }
    if (!backendOnline) {
      setFeedback({ type: 'err', msg: 'Conecta api_puente.py para ejecutar la Fase 3.' });
      return;
    }

    setRunningSinglePhase(true);
    setFeedback({ type: 'info', msg: 'Ejecutando Fase 3 (Agregación y Net Pathway Score)...' });
    try {
      const f1B64 = await archivoABase64(f3InputF1File);
      const f2B64 = await archivoABase64(f3InputF2File);
      const log2B64 = f3InputLog2File ? await archivoABase64(f3InputLog2File) : null;

      const res = await fetch(`${API_URL}/ejecutar-fase3`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          excel_f1_b64: f1B64,
          excel_f2_b64: f2B64,
          excel_log2fc_b64: log2B64,
        }),
      });
      const data = await res.json();
      if (!res.ok || !data.ok) throw new Error(data.error || 'Error en Fase 3');

      setF3SingleResult(data);
      setFeedback({ type: 'ok', msg: `Fase 3 completada. ${data.resumen}` });
    } catch (err: any) {
      setFeedback({ type: 'err', msg: err.message });
    } finally {
      setRunningSinglePhase(false);
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

        {/* MODO PRINCIPAL VS FASES SEPARADAS */}
        <div style={{ display: 'flex', gap: '6px', backgroundColor: '#020617', padding: '4px', borderRadius: '10px', border: '1px solid #1e293b' }}>
          <button
            onClick={() => setModo('auto')}
            style={{
              padding: '7px 14px',
              fontSize: '12px',
              fontWeight: 600,
              borderRadius: '7px',
              border: 'none',
              cursor: 'pointer',
              backgroundColor: modo === 'auto' ? '#14b8a6' : 'transparent',
              color: modo === 'auto' ? '#020617' : '#94a3b8',
            }}
          >
            Ejecución Completa (Fases 1 → 3)
          </button>
          <button
            onClick={() => setModo('fases')}
            style={{
              padding: '7px 14px',
              fontSize: '12px',
              fontWeight: 600,
              borderRadius: '7px',
              border: 'none',
              cursor: 'pointer',
              backgroundColor: modo === 'fases' ? '#14b8a6' : 'transparent',
              color: modo === 'fases' ? '#020617' : '#94a3b8',
            }}
          >
            Ejecución por Fases Separadas
          </button>
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

      {/* =====================================================================
          OPCIÓN POR DEFECTO: EJECUCIÓN COMPLETA AUTOMÁTICA (FASE 1 -> FASE 3)
         ===================================================================== */}
      {modo === 'auto' && (
        <main style={{ flex: 1, padding: '24px', maxWidth: '1720px', width: '100%', margin: '0 auto', boxSizing: 'border-box', display: 'flex', flexDirection: 'column', gap: '24px' }}>

          <section style={{ backgroundColor: '#0f172a', border: '1px solid #1e293b', borderRadius: '16px', padding: '20px' }}>
            <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'space-between', alignItems: 'center', gap: '16px', marginBottom: '16px' }}>
              <div>
                <h2 style={{ margin: '0 0 4px 0', fontSize: '15px', fontWeight: 'bold', display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <FileSpreadsheet size={18} color="#2dd4bf" />
                  <span>Paso 1 · Subir Excel de CIMUS y Seleccionar Rutas de Interés</span>
                </h2>
                <p style={{ margin: 0, fontSize: '12px', color: '#94a3b8' }}>
                  Selecciona las filas que deseas procesar (o marca todo el Excel) y lanza el pipeline completo automáticamente hasta obtener el score final.
                </p>
              </div>

              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', alignItems: 'center' }}>
                <select
                  value={defaultLista}
                  onChange={(e) => setDefaultLista(e.target.value as any)}
                  style={{ padding: '7px 10px', fontSize: '12px', borderRadius: '8px', backgroundColor: '#020617', border: '1px solid #334155', color: '#cbd5e1' }}
                >
                  <option value="Activada">Lista genes UP (Activada)</option>
                  <option value="Suprimida">Lista genes DOWN (Suprimida)</option>
                </select>

                <label style={{ padding: '7px 14px', borderRadius: '8px', border: '1px solid #334155', backgroundColor: '#1e293b', color: '#f8fafc', fontSize: '12px', fontWeight: 500, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <input type="file" accept=".xlsx,.xls,.csv" onChange={(e) => handleAutoExcelUpload(e, false)} style={{ display: 'none' }} />
                  <UploadCloud size={15} color="#2dd4bf" />
                  <span>Subir Excel Completo</span>
                </label>

                <label style={{ padding: '7px 14px', borderRadius: '8px', border: '1px solid #334155', backgroundColor: '#1e293b', color: '#cbd5e1', fontSize: '12px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <input type="file" accept=".xlsx,.xls,.csv" onChange={(e) => handleAutoExcelUpload(e, true)} style={{ display: 'none' }} />
                  <span>+ Añadir 2ª Lista</span>
                </label>

                <button
                  disabled={isRunning || selectedRaw.length === 0}
                  onClick={ejecutarPipelineCompleto}
                  style={{
                    padding: '8px 18px',
                    borderRadius: '8px',
                    border: 'none',
                    backgroundColor: isRunning ? '#0f766e' : '#14b8a6',
                    color: '#020617',
                    fontWeight: 'bold',
                    fontSize: '12px',
                    cursor: isRunning ? 'not-allowed' : 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                  }}
                >
                  {isRunning ? <Loader2 size={16} /> : <Play size={16} />}
                  <span>
                    {isRunning ? 'Ejecutando Fases 1 → 3...' : `Ejecutar Pipeline Completo (${selectedRaw.length} rutas · ${totalSelectedPairs} pares)`}
                  </span>
                </button>
              </div>
            </div>

            {/* BARRA DE PROGRESO */}
            {(isRunning || currentStep > 0) && (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '12px', marginBottom: '16px', backgroundColor: '#020617', padding: '12px', borderRadius: '10px', border: '1px solid #1e293b' }}>
                {[
                  { step: 1, title: 'Fase 1 · Ingesta GO & PubMed', desc: 'Subárbol GO, triaje y descarga abstracts' },
                  { step: 2, title: 'Fase 2 · Inferencia LLM', desc: 'Gemini 3.5 + Groq con citas verificadas' },
                  { step: 3, title: 'Fase 3 · Scoring NPS', desc: 'Aportación por gen y cómputo global' },
                ].map((s) => {
                  const done = currentStep > s.step;
                  const active = currentStep === s.step;
                  return (
                    <div key={s.step} style={{ display: 'flex', alignItems: 'center', gap: '10px', opacity: currentStep >= s.step ? 1 : 0.4 }}>
                      {done ? <CheckCircle2 size={18} color="#34d399" /> : active ? <Loader2 size={18} color="#2dd4bf" /> : <div style={{ width: '18px', height: '18px', borderRadius: '50%', border: '2px solid #475569' }} />}
                      <div>
                        <div style={{ fontSize: '12px', fontWeight: 'bold', color: done ? '#6ee7b7' : active ? '#2dd4bf' : '#cbd5e1' }}>{s.title}</div>
                        <div style={{ fontSize: '11px', color: '#64748b' }}>{s.desc}</div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}

            {/* CONTROLES DE SELECCIÓN */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px', gap: '12px' }}>
              <div style={{ position: 'relative', flex: 1, maxWidth: '420px' }}>
                <Search size={14} color="#64748b" style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)' }} />
                <input
                  type="text"
                  placeholder="Filtrar filas por GO_ID, nombre o gen..."
                  value={searchRaw}
                  onChange={(e) => setSearchRaw(e.target.value)}
                  style={{ width: '100%', padding: '6px 10px 6px 30px', fontSize: '12px', borderRadius: '8px', backgroundColor: '#020617', border: '1px solid #1e293b', color: '#f8fafc', boxSizing: 'border-box' }}
                />
              </div>
              <div style={{ display: 'flex', gap: '8px', alignItems: 'center', fontSize: '12px' }}>
                <span style={{ color: '#94a3b8' }}>Seleccionadas: <strong style={{ color: '#2dd4bf' }}>{selectedRaw.length}</strong> / {rawRows.length}</span>
                <button
                  onClick={() => {
                    const ids = new Set(filteredRaw.map((r) => r.rowId));
                    setRawRows((prev) => prev.map((r) => (ids.has(r.rowId) ? { ...r, selected: true } : r)));
                  }}
                  style={{ padding: '4px 10px', fontSize: '11px', borderRadius: '6px', border: '1px solid #334155', backgroundColor: '#1e293b', color: '#cbd5e1', cursor: 'pointer' }}
                >
                  Seleccionar todas
                </button>
                <button
                  onClick={() => {
                    const ids = new Set(filteredRaw.map((r) => r.rowId));
                    setRawRows((prev) => prev.map((r) => (ids.has(r.rowId) ? { ...r, selected: false } : r)));
                  }}
                  style={{ padding: '4px 10px', fontSize: '11px', borderRadius: '6px', border: '1px solid #334155', backgroundColor: '#1e293b', color: '#cbd5e1', cursor: 'pointer' }}
                >
                  Limpiar selección
                </button>
              </div>
            </div>

            <div style={{ maxHeight: '210px', overflowY: 'auto', border: '1px solid #1e293b', borderRadius: '10px' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px', textAlign: 'left' }}>
                <thead style={{ backgroundColor: '#020617', position: 'sticky', top: 0 }}>
                  <tr style={{ borderBottom: '1px solid #1e293b', color: '#94a3b8' }}>
                    <th style={{ padding: '8px 10px', width: '36px' }}></th>
                    <th style={{ padding: '8px 10px' }}>GO_ID</th>
                    <th style={{ padding: '8px 10px' }}>Descripción</th>
                    <th style={{ padding: '8px 10px' }}>Lista</th>
                    <th style={{ padding: '8px 10px' }}>Genes (geneID)</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredRaw.map((r) => (
                    <tr
                      key={r.rowId}
                      onClick={() => setRawRows((prev) => prev.map((x) => (x.rowId === r.rowId ? { ...x, selected: !x.selected } : x)))}
                      style={{ borderBottom: '1px solid rgba(30, 41, 59, 0.5)', backgroundColor: r.selected ? 'rgba(20, 184, 166, 0.08)' : 'transparent', cursor: 'pointer' }}
                    >
                      <td style={{ padding: '8px 10px', textAlign: 'center' }}>{r.selected ? <CheckSquare size={15} color="#2dd4bf" /> : <Square size={15} color="#475569" />}</td>
                      <td style={{ padding: '8px 10px', fontFamily: 'monospace', fontWeight: 'bold', color: '#2dd4bf' }}>{r.go_id}</td>
                      <td style={{ padding: '8px 10px', color: '#f1f5f9' }}>{r.description}</td>
                      <td style={{ padding: '8px 10px' }}>
                        <span style={{ fontSize: '10px', padding: '2px 6px', borderRadius: '4px', backgroundColor: r.lista === 'Activada' ? 'rgba(16, 185, 129, 0.15)' : 'rgba(244, 63, 94, 0.15)', color: r.lista === 'Activada' ? '#6ee7b7' : '#fda4af' }}>
                          {r.lista}
                        </span>
                      </td>
                      <td style={{ padding: '8px 10px', fontFamily: 'monospace', fontSize: '11px', color: '#94a3b8', maxWidth: '340px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                        <strong>({r.genesList.length})</strong> {r.geneID}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          {/* RESULTADO GLOBAL Y APORTACIÓN POR GEN */}
          <section style={{ display: 'grid', gridTemplateColumns: 'minmax(340px, 460px) 1fr', gap: '24px' }}>
            <div style={{ backgroundColor: '#0f172a', border: '1px solid #1e293b', borderRadius: '16px', padding: '18px', display: 'flex', flexDirection: 'column' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                <div>
                  <h3 style={{ margin: 0, fontSize: '14px', fontWeight: 'bold' }}>Paso 2 · Cómputo Global por Ruta (NPS)</h3>
                  <span style={{ fontSize: '11px', color: '#94a3b8' }}>Haz clic en una ruta para ver el desglose gen a gen</span>
                </div>
                {autoExcelDownload && (
                  <button
                    onClick={() => descargarBase64Excel(autoExcelDownload.b64, autoExcelDownload.name)}
                    style={{ padding: '6px 12px', fontSize: '11px', borderRadius: '6px', border: 'none', backgroundColor: '#14b8a6', color: '#020617', fontWeight: 'bold', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '5px' }}
                  >
                    <Download size={13} />
                    <span>Descargar Excel</span>
                  </button>
                )}
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', overflowY: 'auto', maxHeight: '440px' }}>
                {rutasRes.map((r) => {
                  const selected = r.GO_ID === activePathway?.GO_ID;
                  return (
                    <div
                      key={r.GO_ID}
                      onClick={() => setActiveGoId(r.GO_ID)}
                      style={{
                        padding: '12px 14px',
                        borderRadius: '10px',
                        border: selected ? '1px solid #2dd4bf' : '1px solid #1e293b',
                        backgroundColor: selected ? 'rgba(20, 184, 166, 0.1)' : '#020617',
                        cursor: 'pointer',
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        gap: '10px'
                      }}
                    >
                      <div style={{ minWidth: 0, flex: 1 }}>
                        <span style={{ fontFamily: 'monospace', fontSize: '12px', fontWeight: 'bold', color: '#2dd4bf' }}>{r.GO_ID}</span>
                        <div style={{ fontSize: '12px', fontWeight: 600, color: '#f8fafc', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{r.Ruta_Nombre}</div>
                        <div style={{ fontSize: '11px', color: '#94a3b8', marginTop: '4px', fontFamily: 'monospace' }}>
                          <span style={{ color: '#34d399' }}>+{r.n_activan} activan</span> · <span style={{ color: '#f87171' }}>-{r.n_inhiben} inhiben</span> · Cob. {(Number(r.Cobertura || 0) * 100).toFixed(0)}%
                        </div>
                      </div>
                      <div style={{ textAlign: 'right', flexShrink: 0 }}>
                        <div style={{
                          fontFamily: 'monospace',
                          fontSize: '13px',
                          fontWeight: 'bold',
                          padding: '3px 8px',
                          borderRadius: '6px',
                          backgroundColor: r.Lectura === 'activada' ? 'rgba(6, 78, 59, 0.8)' : r.Lectura === 'inhibida' ? 'rgba(136, 19, 55, 0.8)' : '#1e293b',
                          color: r.Lectura === 'activada' ? '#6ee7b7' : r.Lectura === 'inhibida' ? '#fda4af' : '#fbbf24'
                        }}>
                          NPS {r.NPS !== null && r.NPS !== '' ? (Number(r.NPS) > 0 ? `+${Number(r.NPS).toFixed(2)}` : Number(r.NPS).toFixed(2)) : 'N/A'}
                        </div>
                        <span style={{ fontSize: '10px', textTransform: 'uppercase', color: '#94a3b8', fontWeight: 'bold', display: 'block', marginTop: '3px' }}>{r.Lectura}</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            <div style={{ backgroundColor: '#0f172a', border: '1px solid #1e293b', borderRadius: '16px', padding: '18px', display: 'flex', flexDirection: 'column' }}>
              {activePathway && (
                <>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', borderBottom: '1px solid #1e293b', paddingBottom: '12px', marginBottom: '14px' }}>
                    <div>
                      <span style={{ fontFamily: 'monospace', fontSize: '12px', color: '#2dd4bf', fontWeight: 'bold' }}>{activePathway.GO_ID}</span>
                      <h3 style={{ margin: '2px 0 4px 0', fontSize: '16px', fontWeight: 'bold' }}>{activePathway.Ruta_Nombre}</h3>
                      <span style={{ fontSize: '11px', color: '#94a3b8' }}>Aportación individual: <code>c = signo_funcional × dirección_scRNAseq</code></span>
                    </div>
                    <div style={{ textAlign: 'right' }}>
                      <span style={{ fontSize: '11px', color: '#94a3b8', display: 'block' }}>Lectura Final</span>
                      <span style={{ fontSize: '15px', fontWeight: 'bold', textTransform: 'uppercase', color: activePathway.Lectura === 'activada' ? '#34d399' : activePathway.Lectura === 'inhibida' ? '#f87171' : '#fbbf24' }}>
                        {activePathway.Lectura} ({activePathway.NPS !== null ? Number(activePathway.NPS).toFixed(2) : 'N/A'})
                      </span>
                    </div>
                  </div>

                  <div style={{ overflowX: 'auto' }}>
                    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px', textAlign: 'left' }}>
                      <thead style={{ backgroundColor: '#020617' }}>
                        <tr style={{ borderBottom: '1px solid #1e293b', color: '#94a3b8' }}>
                          <th style={{ padding: '9px' }}>Gen</th>
                          <th style={{ padding: '9px' }}>Expresión (d)</th>
                          <th style={{ padding: '9px' }}>Rol GO / LLM (s)</th>
                          <th style={{ padding: '9px' }}>Aportación (c)</th>
                          <th style={{ padding: '9px' }}>Origen</th>
                          <th style={{ padding: '9px' }}>Evidencia / Justificación</th>
                        </tr>
                      </thead>
                      <tbody>
                        {activeGenes.map((g, idx) => (
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
                              {Number(g.Contribucion) > 0 ? `+${g.Contribucion}` : g.Contribucion}
                            </td>
                            <td style={{ padding: '9px', fontFamily: 'monospace', fontSize: '11px', color: '#94a3b8' }}>{g.Origen}</td>
                            <td style={{ padding: '9px', color: '#cbd5e1', maxWidth: '340px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }} title={`${g.Motivos} | ${g.Votos}`}>
                              {g.Votos || g.Motivos}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </>
              )}
            </div>
          </section>
        </main>
      )}

      {/* =====================================================================
          OPCIÓN SECUNDARIA: EJECUCIÓN INDIVIDUAL POR FASES DESDE EL FRONTEND
         ===================================================================== */}
      {modo === 'fases' && (
        <main style={{ flex: 1, padding: '24px', maxWidth: '1400px', width: '100%', margin: '0 auto', boxSizing: 'border-box', display: 'flex', flexDirection: 'column', gap: '20px' }}>

          {/* SELECTOR DE FASE */}
          <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
            {[
              { id: 'f1', label: 'Fase 1 · Ingesta GO & Abstracts' },
              { id: 'f2', label: 'Fase 2 · Inferencia LLM y Citas' },
              { id: 'f3', label: 'Fase 3 · Scoring Net Pathway Score' },
            ].map((t) => (
              <button
                key={t.id}
                onClick={() => setSubFase(t.id as any)}
                style={{
                  padding: '10px 18px',
                  borderRadius: '10px',
                  border: subFase === t.id ? '1px solid #2dd4bf' : '1px solid #334155',
                  backgroundColor: subFase === t.id ? 'rgba(20, 184, 166, 0.15)' : '#0f172a',
                  color: subFase === t.id ? '#5eead4' : '#94a3b8',
                  fontSize: '13px',
                  fontWeight: 'bold',
                  cursor: 'pointer',
                }}
              >
                {t.label}
              </button>
            ))}
          </div>

          {/* PANEL DE FASE 1 INDIVIDUAL */}
          {subFase === 'f1' && (
            <div style={{ backgroundColor: '#0f172a', border: '1px solid #1e293b', borderRadius: '16px', padding: '24px', display: 'flex', flexDirection: 'column', gap: '18px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '12px' }}>
                <div>
                  <h2 style={{ margin: '0 0 6px 0', fontSize: '17px', fontWeight: 'bold', display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span>Fase 1 · Ingesta de Evidencias GO y Descarga de Abstracts</span>
                    <button
                      onClick={() => setInfoModalKey('f1')}
                      style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', padding: '3px 8px', fontSize: '11px', borderRadius: '999px', border: '1px solid #0284c7', backgroundColor: 'rgba(2, 132, 199, 0.15)', color: '#38bdf8', cursor: 'pointer' }}
                    >
                      <HelpCircle size={13} />
                      <span>¿Qué Excel subir y qué obtendré?</span>
                    </button>
                  </h2>
                  <p style={{ margin: 0, fontSize: '12px', color: '#94a3b8' }}>
                    Sube el Excel crudo de CIMUS (columnas <code>ID</code>, <code>Description</code>, <code>geneID</code>), marca las filas de interés y genera el dataset con el triaje GO y los abstracts de PubMed.
                  </p>
                </div>

                <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap', alignItems: 'center' }}>
                  <select
                    value={f1SingleLista}
                    onChange={(e) => setF1SingleLista(e.target.value as any)}
                    style={{ padding: '7px 10px', fontSize: '12px', borderRadius: '8px', backgroundColor: '#020617', border: '1px solid #334155', color: '#cbd5e1' }}
                  >
                    <option value="Activada">Lista Activada (up)</option>
                    <option value="Suprimida">Lista Suprimida (down)</option>
                  </select>

                  <label style={{ padding: '8px 14px', borderRadius: '8px', border: '1px solid #334155', backgroundColor: '#1e293b', color: '#f8fafc', fontSize: '12px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <input type="file" accept=".xlsx,.xls,.csv" onChange={(e) => handleF1SingleUpload(e, false)} style={{ display: 'none' }} />
                    <UploadCloud size={15} color="#2dd4bf" />
                    <span>Subir Excel CIMUS</span>
                  </label>

                  <label style={{ padding: '8px 14px', borderRadius: '8px', border: '1px solid #334155', backgroundColor: '#1e293b', color: '#cbd5e1', fontSize: '12px', cursor: 'pointer' }}>
                    <input type="file" accept=".xlsx,.xls,.csv" onChange={(e) => handleF1SingleUpload(e, true)} style={{ display: 'none' }} />
                    <span>+ Añadir 2ª Lista</span>
                  </label>

                  <button
                    disabled={runningSinglePhase}
                    onClick={ejecutarFase1Individual}
                    style={{ padding: '8px 18px', borderRadius: '8px', border: 'none', backgroundColor: '#14b8a6', color: '#020617', fontWeight: 'bold', fontSize: '12px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px' }}
                  >
                    {runningSinglePhase ? <Loader2 size={15} /> : <Play size={15} />}
                    <span>Ejecutar Fase 1 ({f1SingleRows.filter((r) => r.selected).length} rutas)</span>
                  </button>
                </div>
              </div>

              {/* Tabla de selección de filas */}
              <div style={{ maxHeight: '220px', overflowY: 'auto', border: '1px solid #1e293b', borderRadius: '10px' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px', textAlign: 'left' }}>
                  <thead style={{ backgroundColor: '#020617', position: 'sticky', top: 0 }}>
                    <tr style={{ borderBottom: '1px solid #1e293b', color: '#94a3b8' }}>
                      <th style={{ padding: '8px 10px', width: '36px' }}></th>
                      <th style={{ padding: '8px 10px' }}>GO_ID</th>
                      <th style={{ padding: '8px 10px' }}>Description</th>
                      <th style={{ padding: '8px 10px' }}>Lista</th>
                      <th style={{ padding: '8px 10px' }}>geneID</th>
                    </tr>
                  </thead>
                  <tbody>
                    {f1SingleRows.map((r) => (
                      <tr
                        key={r.rowId}
                        onClick={() => setF1SingleRows((prev) => prev.map((x) => (x.rowId === r.rowId ? { ...x, selected: !x.selected } : x)))}
                        style={{ borderBottom: '1px solid rgba(30, 41, 59, 0.5)', backgroundColor: r.selected ? 'rgba(20, 184, 166, 0.08)' : 'transparent', cursor: 'pointer' }}
                      >
                        <td style={{ padding: '8px 10px', textAlign: 'center' }}>{r.selected ? <CheckSquare size={15} color="#2dd4bf" /> : <Square size={15} color="#475569" />}</td>
                        <td style={{ padding: '8px 10px', fontFamily: 'monospace', color: '#2dd4bf', fontWeight: 'bold' }}>{r.go_id}</td>
                        <td style={{ padding: '8px 10px' }}>{r.description}</td>
                        <td style={{ padding: '8px 10px' }}>{r.lista}</td>
                        <td style={{ padding: '8px 10px', fontFamily: 'monospace', fontSize: '11px', color: '#94a3b8' }}>{r.geneID}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Resultado Fase 1 y Descarga */}
              {f1SingleResult && (
                <div style={{ backgroundColor: '#020617', border: '1px solid #0f766e', borderRadius: '12px', padding: '16px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                    <div>
                      <span style={{ fontSize: '13px', fontWeight: 'bold', color: '#5eead4', display: 'block' }}>Resultado de Fase 1 generado</span>
                      <span style={{ fontSize: '12px', color: '#cbd5e1' }}>{f1SingleResult.resumen}</span>
                    </div>
                    <button
                      onClick={() => descargarBase64Excel(f1SingleResult.excel_b64, f1SingleResult.nombre_excel)}
                      style={{ padding: '8px 16px', borderRadius: '8px', border: 'none', backgroundColor: '#14b8a6', color: '#020617', fontWeight: 'bold', fontSize: '12px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px' }}
                    >
                      <Download size={15} />
                      <span>Descargar {f1SingleResult.nombre_excel}</span>
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* PANEL DE FASE 2 INDIVIDUAL */}
          {subFase === 'f2' && (
            <div style={{ backgroundColor: '#0f172a', border: '1px solid #1e293b', borderRadius: '16px', padding: '24px', display: 'flex', flexDirection: 'column', gap: '18px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '12px' }}>
                <div>
                  <h2 style={{ margin: '0 0 6px 0', fontSize: '17px', fontWeight: 'bold', display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span>Fase 2 · Inferencia Mecanística con LLM y Verificación de Citas</span>
                    <button
                      onClick={() => setInfoModalKey('f2')}
                      style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', padding: '3px 8px', fontSize: '11px', borderRadius: '999px', border: '1px solid #0284c7', backgroundColor: 'rgba(2, 132, 199, 0.15)', color: '#38bdf8', cursor: 'pointer' }}
                    >
                      <HelpCircle size={13} />
                      <span>¿Qué Excel subir y qué obtendré?</span>
                    </button>
                  </h2>
                  <p style={{ margin: 0, fontSize: '12px', color: '#94a3b8' }}>
                    Sube el archivo <code>fase1_dataset_abstracts.xlsx</code> obtenido en la Fase 1 para evaluar los abstracts con Gemini 3.5 Flash-Lite y respaldo Groq.
                  </p>
                </div>

                <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
                  <label style={{ padding: '8px 14px', borderRadius: '8px', border: '1px solid #334155', backgroundColor: '#1e293b', color: '#f8fafc', fontSize: '12px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <input type="file" accept=".xlsx,.xls" onChange={(e) => setF2InputFile(e.target.files?.[0] || null)} style={{ display: 'none' }} />
                    <UploadCloud size={15} color="#2dd4bf" />
                    <span>{f2InputFile ? f2InputFile.name : 'Subir fase1_dataset_abstracts.xlsx'}</span>
                  </label>

                  <button
                    disabled={runningSinglePhase || !f2InputFile}
                    onClick={ejecutarFase2Individual}
                    style={{ padding: '8px 18px', borderRadius: '8px', border: 'none', backgroundColor: !f2InputFile ? '#334155' : '#14b8a6', color: !f2InputFile ? '#94a3b8' : '#020617', fontWeight: 'bold', fontSize: '12px', cursor: !f2InputFile ? 'not-allowed' : 'pointer', display: 'flex', alignItems: 'center', gap: '6px' }}
                  >
                    {runningSinglePhase ? <Loader2 size={15} /> : <Play size={15} />}
                    <span>Ejecutar Fase 2</span>
                  </button>
                </div>
              </div>

              {f2SingleResult && (
                <div style={{ backgroundColor: '#020617', border: '1px solid #0f766e', borderRadius: '12px', padding: '16px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div>
                      <span style={{ fontSize: '13px', fontWeight: 'bold', color: '#5eead4', display: 'block' }}>Resultado de Fase 2 generado</span>
                      <span style={{ fontSize: '12px', color: '#cbd5e1' }}>{f2SingleResult.resumen}</span>
                    </div>
                    <button
                      onClick={() => descargarBase64Excel(f2SingleResult.excel_b64, f2SingleResult.nombre_excel)}
                      style={{ padding: '8px 16px', borderRadius: '8px', border: 'none', backgroundColor: '#14b8a6', color: '#020617', fontWeight: 'bold', fontSize: '12px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px' }}
                    >
                      <Download size={15} />
                      <span>Descargar {f2SingleResult.nombre_excel}</span>
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* PANEL DE FASE 3 INDIVIDUAL */}
          {subFase === 'f3' && (
            <div style={{ backgroundColor: '#0f172a', border: '1px solid #1e293b', borderRadius: '16px', padding: '24px', display: 'flex', flexDirection: 'column', gap: '18px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '12px' }}>
                <div>
                  <h2 style={{ margin: '0 0 6px 0', fontSize: '17px', fontWeight: 'bold', display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span>Fase 3 · Agregación de Evidencias y Net Pathway Score (NPS)</span>
                    <button
                      onClick={() => setInfoModalKey('f3')}
                      style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', padding: '3px 8px', fontSize: '11px', borderRadius: '999px', border: '1px solid #0284c7', backgroundColor: 'rgba(2, 132, 199, 0.15)', color: '#38bdf8', cursor: 'pointer' }}
                    >
                      <HelpCircle size={13} />
                      <span>¿Qué Excels subir y qué obtendré?</span>
                    </button>
                  </h2>
                  <p style={{ margin: 0, fontSize: '12px', color: '#94a3b8' }}>
                    Combina las salidas de la Fase 1 y Fase 2 (más la tabla opcional de log2FC) para calcular el NPS determinista de cada ruta.
                  </p>
                </div>

                <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap', alignItems: 'center' }}>
                  <label style={{ padding: '8px 12px', borderRadius: '8px', border: '1px solid #334155', backgroundColor: '#1e293b', color: '#f8fafc', fontSize: '12px', cursor: 'pointer' }}>
                    <input type="file" accept=".xlsx,.xls" onChange={(e) => setF3InputF1File(e.target.files?.[0] || null)} style={{ display: 'none' }} />
                    <span>{f3InputF1File ? `F1: ${f3InputF1File.name}` : '1. Subir Excel Fase 1'}</span>
                  </label>

                  <label style={{ padding: '8px 12px', borderRadius: '8px', border: '1px solid #334155', backgroundColor: '#1e293b', color: '#f8fafc', fontSize: '12px', cursor: 'pointer' }}>
                    <input type="file" accept=".xlsx,.xls" onChange={(e) => setF3InputF2File(e.target.files?.[0] || null)} style={{ display: 'none' }} />
                    <span>{f3InputF2File ? `F2: ${f3InputF2File.name}` : '2. Subir Excel Fase 2'}</span>
                  </label>

                  <label style={{ padding: '8px 12px', borderRadius: '8px', border: '1px dashed #334155', backgroundColor: '#020617', color: '#94a3b8', fontSize: '12px', cursor: 'pointer' }}>
                    <input type="file" accept=".xlsx,.xls,.csv" onChange={(e) => setF3InputLog2File(e.target.files?.[0] || null)} style={{ display: 'none' }} />
                    <span>{f3InputLog2File ? `log2FC: ${f3InputLog2File.name}` : '3. Opcional: log2FC'}</span>
                  </label>

                  <button
                    disabled={runningSinglePhase || !f3InputF1File || !f3InputF2File}
                    onClick={ejecutarFase3Individual}
                    style={{ padding: '8px 18px', borderRadius: '8px', border: 'none', backgroundColor: (!f3InputF1File || !f3InputF2File) ? '#334155' : '#14b8a6', color: (!f3InputF1File || !f3InputF2File) ? '#94a3b8' : '#020617', fontWeight: 'bold', fontSize: '12px', cursor: (!f3InputF1File || !f3InputF2File) ? 'not-allowed' : 'pointer', display: 'flex', alignItems: 'center', gap: '6px' }}
                  >
                    {runningSinglePhase ? <Loader2 size={15} /> : <Play size={15} />}
                    <span>Calcular Scoring (Fase 3)</span>
                  </button>
                </div>
              </div>

              {f3SingleResult && (
                <div style={{ backgroundColor: '#020617', border: '1px solid #0f766e', borderRadius: '12px', padding: '16px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div>
                      <span style={{ fontSize: '13px', fontWeight: 'bold', color: '#5eead4', display: 'block' }}>Resultado de Fase 3 generado</span>
                      <span style={{ fontSize: '12px', color: '#cbd5e1' }}>{f3SingleResult.resumen}</span>
                    </div>
                    <button
                      onClick={() => descargarBase64Excel(f3SingleResult.excel_b64, f3SingleResult.nombre_excel)}
                      style={{ padding: '8px 16px', borderRadius: '8px', border: 'none', backgroundColor: '#14b8a6', color: '#020617', fontWeight: 'bold', fontSize: '12px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px' }}
                    >
                      <Download size={15} />
                      <span>Descargar {f3SingleResult.nombre_excel}</span>
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}
        </main>
      )}

      {/* =====================================================================
          VENTANA DE INFORMACIÓN EXPLICATIVA POR FASE (QUÉ SUBIR Y QUÉ SE OBTIENE)
         ===================================================================== */}
      {infoModalKey && (
        <div style={{ position: 'fixed', inset: 0, backgroundColor: 'rgba(2, 6, 23, 0.85)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '16px', zIndex: 50 }}>
          <div style={{ backgroundColor: '#0f172a', border: '1px solid #334155', borderRadius: '16px', maxWidth: '620px', width: '100%', padding: '24px', boxShadow: '0 20px 40px rgba(0,0,0,0.6)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px', borderBottom: '1px solid #1e293b', paddingBottom: '12px' }}>
              <h3 style={{ margin: 0, fontSize: '16px', fontWeight: 'bold', color: '#5eead4' }}>{INFO_FASES[infoModalKey].titulo}</h3>
              <button onClick={() => setInfoModalKey(null)} style={{ background: 'none', border: 'none', color: '#94a3b8', cursor: 'pointer' }}>
                <X size={18} />
              </button>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '14px', fontSize: '13px', lineHeight: '1.5' }}>
              <div>
                <strong style={{ color: '#38bdf8', display: 'block', marginBottom: '4px' }}>1. Fichero Excel requerido:</strong>
                <span style={{ color: '#e2e8f0' }}>{INFO_FASES[infoModalKey].entrada}</span>
              </div>

              <div>
                <strong style={{ color: '#38bdf8', display: 'block', marginBottom: '4px' }}>2. Estructura y columnas obligatorias:</strong>
                <ul style={{ margin: 0, paddingLeft: '18px', color: '#cbd5e1' }}>
                  {INFO_FASES[infoModalKey].columnas.map((c, idx) => (
                    <li key={idx} style={{ marginBottom: '3px' }}>{c}</li>
                  ))}
                </ul>
              </div>

              <div>
                <strong style={{ color: '#38bdf8', display: 'block', marginBottom: '4px' }}>3. Qué hace esta fase internamente:</strong>
                <span style={{ color: '#cbd5e1' }}>{INFO_FASES[infoModalKey].proceso}</span>
              </div>

              <div style={{ backgroundColor: '#020617', border: '1px solid #0f766e', borderRadius: '10px', padding: '12px' }}>
                <strong style={{ color: '#2dd4bf', display: 'block', marginBottom: '4px' }}>4. Resultado descargable que vas a obtener:</strong>
                <span style={{ color: '#f1f5f9' }}>{INFO_FASES[infoModalKey].salida}</span>
              </div>
            </div>

            <div style={{ marginTop: '20px', textAlign: 'right' }}>
              <button
                onClick={() => setInfoModalKey(null)}
                style={{ padding: '8px 18px', borderRadius: '8px', border: 'none', backgroundColor: '#14b8a6', color: '#020617', fontWeight: 'bold', fontSize: '12px', cursor: 'pointer' }}
              >
                Entendido
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}