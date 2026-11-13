import React, { useState, useMemo } from 'react';
import {
  Dna,
  UploadCloud,
  FileSpreadsheet,
  Search,
  Sparkles,
  BookOpen,
  Code2,
  ArrowUpRight,
  ArrowDownRight,
  RefreshCw,
  Info,
  Microscope,
  ShieldCheck,
  Layers
} from 'lucide-react';

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

interface GeneItem {
  symbol: string;
  direccion: 'up' | 'down';
  log2fc: number;
  signo_par: '+1' | '-1' | 'neutro' | 'UNKNOWN';
  estado_par: string;
  contribucion: number;
  origen: string;
  freno: boolean;
  motivos: string;
  evidencia: string;
  confianza: number;
}

interface PathwayItem {
  go_id: string;
  name: string;
  listas: string;
  context: string;
  totalGenes: number;
  n_activan: number;
  n_inhiben: number;
  n_neutros: number;
  n_revisar: number;
  nps: number | null;
  nps_con_revisar: number | null;
  lectura: string;
  cobertura: number;
  fraccion_neutros: number;
  genes: GeneItem[];
  resumen_ia?: {
    modelos: string;
    cita_clave: string;
    explicacion: string;
  };
}

const DEMO_PATHWAYS: PathwayItem[] = [
  {
    go_id: "GO:0002443",
    name: "leukocyte mediated immunity",
    listas: "ambas",
    context: "Células NK en HNSC (Laringe/Faringe)",
    totalGenes: 18,
    n_activan: 9,
    n_inhiben: 4,
    n_neutros: 2,
    n_revisar: 2,
    nps: 0.38,
    nps_con_revisar: 0.31,
    lectura: "activada",
    cobertura: 0.83,
    fraccion_neutros: 0.13,
    genes: [
      {
        symbol: "CD7",
        direccion: "up",
        log2fc: 1.82,
        signo_par: "UNKNOWN",
        estado_par: "revisar",
        contribucion: 0,
        origen: "LLM",
        freno: false,
        motivos: "baja_confianza | discrepancia_polaridad_GO",
        evidencia: "PMID 10652336: Efecto mediado por ligando K12-Fc, no receptor CD7 intrínseco.",
        confianza: 35
      },
      {
        symbol: "PRF1",
        direccion: "up",
        log2fc: 2.45,
        signo_par: "+1",
        estado_par: "resuelto",
        contribucion: 2.45,
        origen: "GO",
        freno: false,
        motivos: "coincide_polaridad_GO",
        evidencia: "GO:0001775: Componente de maquinaria citolítica en células NK.",
        confianza: 95
      },
      {
        symbol: "GZMB",
        direccion: "up",
        log2fc: 2.10,
        signo_par: "+1",
        estado_par: "resuelto",
        contribucion: 2.10,
        origen: "LLM",
        freno: false,
        motivos: "acuerdo_modelos",
        evidencia: "PMID 28456102: 'Granzyme B delivers cytotoxic punch driving target apoptosis.'",
        confianza: 92
      },
      {
        symbol: "TGFB1",
        direccion: "up",
        log2fc: 1.40,
        signo_par: "-1",
        estado_par: "resuelto",
        contribucion: -1.40,
        origen: "LLM",
        freno: true,
        motivos: "freno_retroalimentacion",
        evidencia: "PMID 31092833: 'TGF-beta impairs NK cell degranulation and interferon secretion.'",
        confianza: 88
      },
      {
        symbol: "IGKC",
        direccion: "up",
        log2fc: 1.15,
        signo_par: "neutro",
        estado_par: "resuelto",
        contribucion: 0,
        origen: "Ig",
        freno: false,
        motivos: "inmunoglobulina",
        evidencia: "HGNC Inmunoglobulina: evaluada como neutra (función de Ig completa, UniProt).",
        confianza: 100
      }
    ],
    resumen_ia: {
      modelos: "Gemini 3.5 Flash-Lite / gpt-oss-120b",
      cita_clave: "Granzyme B delivers cytotoxic punch driving target apoptosis (PMID: 28456102)",
      explicacion: "A pesar de la sobreexpresión de ligandos inmunosupresores como TGFB1 (marcado como freno) y la discrepancia en CD7, la ruta presenta un Net Pathway Score de +0.38 con cobertura del 83%, resolviéndose como funcionalmente ACTIVADA en las células NK del microambiente laríngeo."
    }
  },
  {
    go_id: "GO:0001912",
    name: "positive regulation of leukocyte mediated cytotoxicity",
    listas: "ambas",
    context: "Microambiente hipóxico tumoral (HNSC)",
    totalGenes: 12,
    n_activan: 3,
    n_inhiben: 6,
    n_neutros: 1,
    n_revisar: 1,
    nps: -0.45,
    nps_con_revisar: -0.48,
    lectura: "inhibida",
    cobertura: 0.78,
    fraccion_neutros: 0.10,
    genes: [
      {
        symbol: "KLRC1",
        direccion: "up",
        log2fc: 1.95,
        signo_par: "-1",
        estado_par: "resuelto",
        contribucion: -1.95,
        origen: "LLM",
        freno: true,
        motivos: "freno_retroalimentacion",
        evidencia: "PMID 30987411: 'NKG2A (KLRC1) engagement transmits inhibitory cascade suppressing lysis.'",
        confianza: 91
      },
      {
        symbol: "FCGR3A",
        direccion: "down",
        log2fc: -1.75,
        signo_par: "+1",
        estado_par: "resuelto",
        contribucion: -1.75,
        origen: "GO",
        freno: false,
        motivos: "aceptado_por_GO",
        evidencia: "Anotación experimental GAF: mediador directo de citotoxicidad ADCC en NK humanas.",
        confianza: 94
      }
    ],
    resumen_ia: {
      modelos: "Gemini 3.5 Flash-Lite / gpt-oss-120b",
      cita_clave: "NKG2A engagement transmits inhibitory cascade suppressing lysis (PMID: 30987411)",
      explicacion: "La reducción de FCGR3A junto a la sobreexpresión del checkpoint inhibitorio NKG2A genera un NPS de -0.45, concluyendo en INHIBICIÓN neta."
    }
  }
];

export default function App() {
  const [pathways, setPathways] = useState<PathwayItem[]>(DEMO_PATHWAYS);
  const [selectedPathwayId, setSelectedPathwayId] = useState<string>(DEMO_PATHWAYS[0].go_id);
  const [searchTerm, setSearchTerm] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [showArchModal, setShowArchModal] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);

  const selectedPathway = useMemo(() => {
    return pathways.find(p => p.go_id === selectedPathwayId) || pathways[0];
  }, [pathways, selectedPathwayId]);

  const filteredPathways = useMemo(() => {
    return pathways.filter(p => {
      const matchSearch = p.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
                          p.go_id.toLowerCase().includes(searchTerm.toLowerCase());
      const matchStatus = statusFilter === "all" ? true : p.lectura.toLowerCase() === statusFilter.toLowerCase();
      return matchSearch && matchStatus;
    });
  }, [pathways, searchTerm, statusFilter]);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    try {
      setFeedback("Cargando y parseando archivo...");
      const XLSX = await loadXLSX();
      const reader = new FileReader();

      reader.onload = (evt) => {
        try {
          const data = evt.target?.result;
          const workbook = XLSX.read(data, { type: 'binary' });

          if (workbook.SheetNames.includes("Por_ruta")) {
            const rutaRows: any[] = XLSX.utils.sheet_to_json(workbook.Sheets["Por_ruta"]);
            const parRows: any[] = workbook.SheetNames.includes("Por_par")
              ? XLSX.utils.sheet_to_json(workbook.Sheets["Por_par"])
              : [];

            const parsedList: PathwayItem[] = rutaRows.map((r, idx) => {
              const goId = r.GO_ID || `GO:000000${idx}`;
              const pGenes: GeneItem[] = parRows
                .filter((p: any) => p.GO_ID === goId)
                .map((p: any) => ({
                  symbol: p.Gen || 'GEN',
                  direccion: (p.Direccion || 'up').toLowerCase(),
                  log2fc: Number(p.Log2FC || 1.0),
                  signo_par: p.Signo_par || 'UNKNOWN',
                  estado_par: p.Estado_par || 'no_concluyente',
                  contribucion: Number(p.Contribucion || 0),
                  origen: p.Origen || 'ninguno',
                  freno: Boolean(p.Freno_retroalimentacion),
                  motivos: p.Motivos || '',
                  evidencia: p.Votos || 'Sin votos registrados',
                  confianza: 85
                }));

              return {
                go_id: goId,
                name: r.Ruta_Nombre || 'Ruta sin descripción',
                listas: (r.Listas || 'ambas').toLowerCase(),
                context: "Células NK (scRNA-seq HNSC)",
                totalGenes: Number(r.n_total || pGenes.length),
                n_activan: Number(r.n_activan || 0),
                n_inhiben: Number(r.n_inhiben || 0),
                n_neutros: Number(r.n_neutros || 0),
                n_revisar: Number(r.n_revisar || 0),
                nps: r.NPS !== undefined && r.NPS !== null ? Number(r.NPS) : null,
                nps_con_revisar: r.NPS_con_revisar !== undefined ? Number(r.NPS_con_revisar) : null,
                lectura: (r.Lectura || 'insuficiente').toLowerCase(),
                cobertura: Number(r.Cobertura || 0),
                fraccion_neutros: Number(r.Fraccion_neutros || 0),
                genes: pGenes,
                resumen_ia: {
                  modelos: "Gemini 3.5 Flash-Lite / gpt-oss-120b",
                  cita_clave: "Agregación cuantitativa determinista (Fase 3 Scoring)",
                  explicacion: `NPS neto calculado: ${r.NPS !== undefined ? Number(r.NPS).toFixed(2) : 'N/A'} con clasificación '${r.Lectura}'.`
                }
              };
            });

            if (parsedList.length > 0) {
              setPathways(parsedList);
              setSelectedPathwayId(parsedList[0].go_id);
              setFeedback(`¡Éxito! ${parsedList.length} rutas cargadas desde fase3_scoring.xlsx.`);
              return;
            }
          }
          setFeedback("Archivo cargado, pero no contiene la hoja 'Por_ruta'.");
        } catch (err: any) {
          setFeedback(`Error al procesar: ${err.message}`);
        }
      };

      reader.readAsBinaryString(file);
    } catch (err: any) {
      setFeedback(`Error general: ${err.message}`);
    }
  };

  return (
    <div style={{ minHeight: '100vh', backgroundColor: '#020617', color: '#f8fafc', display: 'flex', flexDirection: 'column' }}>

      {/* HEADER */}
      <header style={{ borderBottom: '1px solid #1e293b', backgroundColor: 'rgba(15, 23, 42, 0.95)', padding: '14px 24px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{ width: '40px', height: '40px', borderRadius: '10px', backgroundColor: '#14b8a6', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#020617' }}>
            <Microscope size={22} />
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ fontSize: '16px', fontWeight: 'bold' }}>CU-01 PathScore Explorer</span>
              <span style={{ fontSize: '11px', padding: '2px 8px', borderRadius: '999px', backgroundColor: 'rgba(20, 184, 166, 0.1)', color: '#5eead4', border: '1px solid rgba(20, 184, 166, 0.2)' }}>
                scRNA-seq NK · HNSC
              </span>
            </div>
            <p style={{ margin: 0, fontSize: '12px', color: '#94a3b8' }}>Reinterpretación de rutas enriquecidas (CIMUS) mediante IA</p>
          </div>
        </div>

        <div style={{ display: 'flex', gap: '10px' }}>
          <button
            onClick={() => setShowArchModal(true)}
            style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '6px 12px', fontSize: '12px', borderRadius: '8px', border: '1px solid #334155', backgroundColor: '#1e293b', color: '#cbd5e1', cursor: 'pointer' }}
          >
            <Layers size={14} color="#38bdf8" />
            <span>Arquitectura CLI</span>
          </button>
          <button
            onClick={() => {
              setPathways(DEMO_PATHWAYS);
              setSelectedPathwayId(DEMO_PATHWAYS[0].go_id);
              setFeedback("Dataset de demostración restaurado.");
            }}
            style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '6px 12px', fontSize: '12px', borderRadius: '8px', border: '1px solid #334155', backgroundColor: '#1e293b', color: '#cbd5e1', cursor: 'pointer' }}
          >
            <RefreshCw size={14} color="#2dd4bf" />
            <span>Datos Demo</span>
          </button>
        </div>
      </header>

      {/* CUERPO PRINCIPAL */}
      <main style={{ flex: 1, padding: '24px', display: 'grid', gridTemplateColumns: 'minmax(320px, 460px) 1fr', gap: '24px', maxWidth: '1700px', width: '100%', margin: '0 auto', boxSizing: 'border-box' }}>

        {/* PANEL IZQUIERDO */}
        <section style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>

          {/* Card de carga */}
          <div style={{ backgroundColor: '#0f172a', border: '1px solid #1e293b', borderRadius: '16px', padding: '16px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <FileSpreadsheet size={16} color="#2dd4bf" />
                <span style={{ fontSize: '12px', fontWeight: 'bold', textTransform: 'uppercase', color: '#cbd5e1' }}>Cargar Archivo Local</span>
              </div>
              <span style={{ fontSize: '11px', color: '#64748b', fontFamily: 'monospace' }}>fase3_scoring.xlsx</span>
            </div>

            <label style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', border: '2px dashed #334155', borderRadius: '12px', padding: '16px', cursor: 'pointer', backgroundColor: 'rgba(2, 6, 23, 0.4)' }}>
              <input type="file" accept=".xlsx,.xls,.csv" onChange={handleFileUpload} style={{ display: 'none' }} />
              <UploadCloud size={24} color="#94a3b8" style={{ marginBottom: '6px' }} />
              <span style={{ fontSize: '12px', color: '#cbd5e1', fontWeight: 500 }}>Arrastra fase3_scoring.xlsx o haz clic</span>
              <span style={{ fontSize: '10px', color: '#64748b', marginTop: '2px' }}>Sin bases de datos · Carga 100% en cliente</span>
            </label>

            {feedback && (
              <div style={{ marginTop: '10px', padding: '8px 12px', borderRadius: '8px', fontSize: '12px', backgroundColor: 'rgba(20, 184, 166, 0.1)', border: '1px solid #0f766e', color: '#5eead4', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Info size={14} />
                <span>{feedback}</span>
              </div>
            )}
          </div>

          {/* Listado de rutas */}
          <div style={{ backgroundColor: '#0f172a', border: '1px solid #1e293b', borderRadius: '16px', flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
            <div style={{ padding: '16px', borderBottom: '1px solid #1e293b' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
                <span style={{ fontSize: '14px', fontWeight: 600 }}>Rutas Enriquecidas ({filteredPathways.length})</span>
              </div>
              <div style={{ display: 'flex', gap: '8px' }}>
                <div style={{ position: 'relative', flex: 1 }}>
                  <Search size={14} color="#64748b" style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)' }} />
                  <input
                    type="text"
                    placeholder="Filtrar por GO o nombre..."
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    style={{ width: '100%', padding: '6px 10px 6px 30px', fontSize: '12px', borderRadius: '8px', backgroundColor: '#020617', border: '1px solid #1e293b', color: '#f8fafc', boxSizing: 'border-box' }}
                  />
                </div>
                <select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                  style={{ fontSize: '12px', padding: '6px 8px', borderRadius: '8px', backgroundColor: '#020617', border: '1px solid #1e293b', color: '#cbd5e1' }}
                >
                  <option value="all">Todas</option>
                  <option value="activada">Activada</option>
                  <option value="inhibida">Inhibida</option>
                </select>
              </div>
            </div>

            <div style={{ flex: 1, overflowY: 'auto', maxHeight: '520px' }}>
              {filteredPathways.map((p) => {
                const isSelected = p.go_id === selectedPathway.go_id;
                return (
                  <div
                    key={p.go_id}
                    onClick={() => setSelectedPathwayId(p.go_id)}
                    style={{
                      padding: '14px 16px',
                      cursor: 'pointer',
                      borderBottom: '1px solid rgba(30, 41, 59, 0.6)',
                      borderLeft: isSelected ? '4px solid #2dd4bf' : '4px solid transparent',
                      backgroundColor: isSelected ? 'rgba(20, 184, 166, 0.1)' : 'transparent',
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      gap: '12px'
                    }}
                  >
                    <div style={{ minWidth: 0, flex: 1 }}>
                      <div style={{ display: 'flex', gap: '8px', alignItems: 'center', marginBottom: '4px' }}>
                        <span style={{ fontFamily: 'monospace', fontSize: '12px', color: '#2dd4bf', fontWeight: 'bold' }}>{p.go_id}</span>
                        <span style={{ fontSize: '10px', padding: '1px 6px', borderRadius: '4px', backgroundColor: '#1e293b', color: '#94a3b8' }}>{p.listas}</span>
                      </div>
                      <div style={{ fontSize: '12px', fontWeight: 600, color: '#f1f5f9', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{p.name}</div>
                    </div>
                    <div style={{ textAlign: 'right', flexShrink: 0 }}>
                      <div style={{
                        fontFamily: 'monospace',
                        fontSize: '11px',
                        fontWeight: 'bold',
                        padding: '2px 6px',
                        borderRadius: '4px',
                        backgroundColor: p.lectura === 'activada' ? 'rgba(6, 78, 59, 0.8)' : p.lectura === 'inhibida' ? 'rgba(136, 19, 55, 0.8)' : '#1e293b',
                        color: p.lectura === 'activada' ? '#6ee7b7' : p.lectura === 'inhibida' ? '#fda4af' : '#cbd5e1'
                      }}>
                        NPS: {p.nps !== null ? (p.nps > 0 ? `+${p.nps.toFixed(2)}` : p.nps.toFixed(2)) : 'N/A'}
                      </div>
                      <span style={{ fontSize: '10px', color: '#94a3b8', textTransform: 'uppercase', display: 'block', marginTop: '2px' }}>{p.lectura}</span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </section>

        {/* PANEL DERECHO */}
        <section style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>

          {/* Card Resumen de la ruta */}
          <div style={{ backgroundColor: '#0f172a', border: '1px solid #1e293b', borderRadius: '16px', padding: '20px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '16px' }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
                  <span style={{ fontSize: '12px', padding: '2px 8px', borderRadius: '4px', backgroundColor: 'rgba(20, 184, 166, 0.1)', border: '1px solid rgba(20, 184, 166, 0.2)', color: '#5eead4', fontFamily: 'monospace', fontWeight: 'bold' }}>
                    {selectedPathway.go_id}
                  </span>
                  <span style={{ fontSize: '12px', color: '#94a3b8' }}>Contexto: <strong style={{ color: '#cbd5e1' }}>{selectedPathway.context}</strong></span>
                </div>
                <h2 style={{ margin: '4px 0 8px 0', fontSize: '18px', fontWeight: 'bold', color: '#ffffff' }}>{selectedPathway.name}</h2>
                <p style={{ margin: 0, fontSize: '12px', color: '#94a3b8', maxWidth: '600px' }}>
                  Cálculo del Net Pathway Score mediante la integración del signo cualitativo inferido (+1, -1, neutro) con la dirección del scRNA-seq.
                </p>
              </div>

              <div style={{ backgroundColor: '#020617', border: '1px solid #1e293b', borderRadius: '12px', padding: '12px 16px', textAlign: 'right', minWidth: '150px' }}>
                <span style={{ fontSize: '10px', textTransform: 'uppercase', color: '#94a3b8', fontWeight: 600 }}>Net Pathway Score</span>
                <div style={{
                  fontSize: '24px',
                  fontFamily: 'monospace',
                  fontWeight: 'bold',
                  margin: '4px 0',
                  color: selectedPathway.lectura === 'activada' ? '#34d399' : selectedPathway.lectura === 'inhibida' ? '#f87171' : '#fbbf24'
                }}>
                  {selectedPathway.nps !== null ? (selectedPathway.nps > 0 ? `+${selectedPathway.nps.toFixed(2)}` : selectedPathway.nps.toFixed(2)) : 'N/A'}
                </div>
                <span style={{ fontSize: '10px', color: '#94a3b8' }}>Cobertura: {(selectedPathway.cobertura * 100).toFixed(0)}%</span>
              </div>
            </div>
          </div>

          {/* Card Explicación IA */}
          {selectedPathway.resumen_ia && (
            <div style={{ backgroundColor: 'rgba(15, 23, 42, 0.8)', border: '1px solid rgba(20, 184, 166, 0.3)', borderRadius: '16px', padding: '16px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Sparkles size={16} color="#2dd4bf" />
                  <span style={{ fontSize: '12px', fontWeight: 'bold', textTransform: 'uppercase', color: '#5eead4' }}>Resolución Bioinformática</span>
                </div>
                <span style={{ fontSize: '11px', fontFamily: 'monospace', color: '#2dd4bf' }}>{selectedPathway.resumen_ia.modelos}</span>
              </div>
              <p style={{ margin: '0 0 10px 0', fontSize: '12px', color: '#cbd5e1', lineHeight: '1.5' }}>
                {selectedPathway.resumen_ia.explicacion}
              </p>
              <div style={{ borderTop: '1px solid #1e293b', paddingTop: '8px', display: 'flex', alignItems: 'center', gap: '8px', fontSize: '11px', color: '#94a3b8' }}>
                <BookOpen size={14} color="#64748b" />
                <span style={{ fontStyle: 'italic', color: '#5eead4' }}>"{selectedPathway.resumen_ia.cita_clave}"</span>
              </div>
            </div>
          )}

          {/* Tabla de Genes */}
          <div style={{ backgroundColor: '#0f172a', border: '1px solid #1e293b', borderRadius: '16px', padding: '16px', flex: 1, display: 'flex', flexDirection: 'column' }}>
            <h3 style={{ margin: '0 0 12px 0', fontSize: '14px', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Dna size={16} color="#38bdf8" />
              <span>Desglose de Genes Evaluados ({selectedPathway.genes.length})</span>
            </h3>

            <div style={{ overflowX: 'auto', flex: 1 }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px', textAlign: 'left' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid #1e293b', color: '#94a3b8' }}>
                    <th style={{ padding: '8px' }}>Gen</th>
                    <th style={{ padding: '8px' }}>scRNA-seq (d)</th>
                    <th style={{ padding: '8px' }}>Signo ($s$)</th>
                    <th style={{ padding: '8px' }}>Contribución</th>
                    <th style={{ padding: '8px' }}>Origen</th>
                    <th style={{ padding: '8px' }}>Evidencia / Cita</th>
                  </tr>
                </thead>
                <tbody>
                  {selectedPathway.genes.map((g, idx) => (
                    <tr key={idx} style={{ borderBottom: '1px solid rgba(30, 41, 59, 0.4)' }}>
                      <td style={{ padding: '10px 8px', fontFamily: 'monospace', fontWeight: 'bold', color: '#f8fafc' }}>
                        {g.symbol}
                        {g.freno && (
                          <span style={{ marginLeft: '6px', fontSize: '9px', padding: '2px 4px', borderRadius: '4px', backgroundColor: 'rgba(245, 158, 11, 0.2)', color: '#fbbf24', border: '1px solid rgba(245, 158, 11, 0.3)' }}>
                            Freno
                          </span>
                        )}
                      </td>
                      <td style={{ padding: '10px 8px', fontFamily: 'monospace' }}>
                        <span style={{
                          padding: '2px 6px',
                          borderRadius: '4px',
                          fontSize: '10px',
                          fontWeight: 600,
                          backgroundColor: g.direccion === 'up' ? 'rgba(6, 78, 59, 0.6)' : 'rgba(136, 19, 55, 0.6)',
                          color: g.direccion === 'up' ? '#6ee7b7' : '#fda4af'
                        }}>
                          {g.direccion.toUpperCase()} ({g.log2fc > 0 ? `+${g.log2fc}` : g.log2fc})
                        </span>
                      </td>
                      <td style={{ padding: '10px 8px', fontFamily: 'monospace', fontWeight: 'bold' }}>
                        <span style={{
                          padding: '2px 6px',
                          borderRadius: '4px',
                          backgroundColor: g.signo_par === '+1' ? 'rgba(20, 184, 166, 0.2)' : g.signo_par === '-1' ? 'rgba(244, 63, 94, 0.2)' : '#1e293b',
                          color: g.signo_par === '+1' ? '#2dd4bf' : g.signo_par === '-1' ? '#fb7185' : '#cbd5e1'
                        }}>
                          {g.signo_par}
                        </span>
                      </td>
                      <td style={{ padding: '10px 8px', fontFamily: 'monospace', fontWeight: 'bold', color: g.contribucion > 0 ? '#34d399' : g.contribucion < 0 ? '#f87171' : '#64748b' }}>
                        {g.contribucion > 0 ? `+${g.contribucion.toFixed(2)}` : g.contribucion.toFixed(2)}
                      </td>
                      <td style={{ padding: '10px 8px' }}>
                        <span style={{ fontSize: '10px', fontFamily: 'monospace', padding: '2px 6px', borderRadius: '4px', backgroundColor: '#1e293b', color: '#94a3b8' }}>
                          {g.origen}
                        </span>
                      </td>
                      <td style={{ padding: '10px 8px', color: '#cbd5e1', maxWidth: '320px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }} title={g.evidencia}>
                        {g.evidencia}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </section>
      </main>

      {/* MODAL CLI */}
      {showArchModal && (
        <div style={{ position: 'fixed', inset: 0, backgroundColor: 'rgba(2, 6, 23, 0.8)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '16px', zIndex: 50 }}>
          <div style={{ backgroundColor: '#0f172a', border: '1px solid #1e293b', borderRadius: '16px', maxWidth: '580px', width: '100%', padding: '20px' }}>
            <h3 style={{ margin: '0 0 12px 0', fontSize: '14px', fontWeight: 'bold', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Code2 size={16} color="#2dd4bf" />
              <span>Ejecución del Pipeline CLI (codigo/)</span>
            </h3>
            <div style={{ backgroundColor: '#020617', border: '1px solid #1e293b', borderRadius: '8px', padding: '12px', fontFamily: 'monospace', fontSize: '12px', color: '#cbd5e1', lineHeight: '1.6' }}>
              <span style={{ color: '#2dd4bf' }}># 1. Ingesta OBO + GAF:</span><br />
              python fase1_ingesta/main.py<br /><br />
              <span style={{ color: '#2dd4bf' }}># 2. Inferencia LLM con validación de citas:</span><br />
              python -m fase2_inferencia ejecutar --solo-respaldo<br /><br />
              <span style={{ color: '#2dd4bf' }}># 3. Scoring determinista Net Pathway Score:</span><br />
              python -m fase3_scoring
            </div>
            <button
              onClick={() => setShowArchModal(false)}
              style={{ marginTop: '16px', float: 'right', padding: '6px 16px', borderRadius: '8px', backgroundColor: '#14b8a6', border: 'none', color: '#020617', fontWeight: 600, fontSize: '12px', cursor: 'pointer' }}
            >
              Cerrar
            </button>
          </div>
        </div>
      )}
    </div>
  );
}