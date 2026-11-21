// Utilidades que comparten App.tsx y ExcelResultados.tsx

export type Fila = Record<string, unknown>;

// Lo mínimo de SheetJS que se usa (se carga desde el CDN solo cuando hace falta leer o escribir un Excel)
export interface Libro {
  SheetNames: string[];
  Sheets: Record<string, unknown>;
}

export interface LibXLSX {
  read: (data: ArrayBuffer, opts: { type: 'array' }) => Libro;
  write: (libro: Libro, opts: { type: 'array'; bookType: 'xlsx' }) => ArrayBuffer;
  utils: {
    sheet_to_json: (hoja: unknown, opts?: { defval?: unknown }) => Fila[];
    json_to_sheet: (filas: Fila[], opts?: { header?: string[] }) => unknown;
    book_new: () => Libro;
  };
}
type VentanaConXLSX = Window & { XLSX?: LibXLSX };

export const loadXLSX = (): Promise<LibXLSX> => {
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

export const mensaje = (err: unknown) => (err instanceof Error ? err.message : String(err));

export const formatoNPS = (v: number | null | undefined) =>
  v === null || v === undefined ? 'N/A' : v > 0 ? `+${v.toFixed(2)}` : v.toFixed(2).replace('-', '−');

export const colorLectura = (l: string) =>
  l === 'activada' ? 'var(--c-34d399)' : l === 'inhibida' ? 'var(--c-f87171)' : 'var(--c-fbbf24)';
