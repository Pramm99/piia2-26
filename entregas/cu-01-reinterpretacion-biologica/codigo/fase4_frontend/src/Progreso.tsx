// Progreso de la ejecución de una ruta: rueda animada, barra con el porcentaje y contador de tiempo.
// El puente solo dice en qué fase va (GET /estado), así que el porcentaje se estima: cada fase tiene su tramo de la
// barra y, dentro de él, avanza deprisa al principio y cada vez más despacio, sin llegar nunca al final del tramo.
// Salta al tramo siguiente cuando el puente cambia de fase, y solo marca 100 % cuando la ruta ha terminado.
import { useEffect, useState } from 'react';
import { CheckCircle2 } from 'lucide-react';

// fase -> [inicio %, fin %, segundos para recorrer ~63 % del tramo]. En frío la Fase 1 y la 2 tardan del orden de
// un minuto cada una y la 3 un par de segundos (docs/kpis.md); con las cachés, la Fase 1 unos 7 s y las otras ~1 s.
// Con estas constantes, la Fase 1 va por el 17 % a los 7 s y por el 37 % al minuto; la 2, por el 86 % al minuto.
const TRAMOS: Record<number, [number, number, number]> = { 1: [0, 40, 12], 2: [40, 92, 20], 3: [92, 99, 2] };

const reloj = (s: number) => `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(Math.floor(s % 60)).padStart(2, '0')}`;

const porcentaje = (fase: number, segundosEnFase: number) => {
  if (fase >= 4) return 100;
  const [ini, fin, tau] = TRAMOS[fase] || [0, 0, 1];
  return ini + (fin - ini) * 0.95 * (1 - Math.exp(-Math.max(segundosEnFase, 0) / tau));
};

// Rueda de carga: un anillo con degradado que gira y un punto que late en el centro
export function Girador({ size = 18, color = 'var(--c-2dd4bf)' }: { size?: number; color?: string }) {
  return (
    <span className="girador" role="status" aria-label="Cargando" style={{ width: size, height: size, ['--girador-color' as string]: color }}>
      <span className="girador-anillo" />
      <span className="girador-punto" />
    </span>
  );
}

interface Props {
  fase: number; // 1-3 en curso, 4 terminado
  corriendo: boolean;
  inicio: number; // ms del arranque de la ruta
  inicioFase: number; // ms en que el puente informó de la fase en curso
  nombreFase: string;
  totalFinal: number | null; // segundos que midió el puente, al terminar
}

export default function Progreso({ fase, corriendo, inicio, inicioFase, nombreFase, totalFinal }: Props) {
  const [ahora, setAhora] = useState(inicio);
  useEffect(() => {
    if (!corriendo) return;
    const id = setInterval(() => setAhora(Date.now()), 200);
    return () => clearInterval(id);
  }, [corriendo]);

  const terminado = fase >= 4 && !corriendo;
  const pct = terminado ? 100 : porcentaje(fase, (ahora - inicioFase) / 1000);
  const total = terminado && totalFinal !== null ? totalFinal : Math.max(0, (ahora - inicio) / 1000);
  const enFase = Math.max(0, (ahora - inicioFase) / 1000);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
      <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: '8px 16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', minWidth: 0 }}>
          {terminado ? <CheckCircle2 size={22} color="var(--c-34d399)" /> : <Girador size={22} />}
          <div style={{ minWidth: 0 }}>
            <div style={{ fontSize: '13px', fontWeight: 'bold', color: terminado ? 'var(--c-6ee7b7)' : 'var(--c-2dd4bf)' }}>
              {terminado ? 'Ruta ejecutada' : `Fase ${fase} de 3 · ${nombreFase}`}
            </div>
            <div style={{ fontSize: '11px', color: 'var(--c-64748b)' }}>
              {terminado ? 'Fases 1, 2 y 3 completadas' : `Esta fase lleva ${reloj(enFase)}`}
            </div>
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: '12px', fontVariantNumeric: 'tabular-nums' }}>
          <span title="Estimado: el puente informa de la fase en curso, no del avance dentro de cada fase" style={{ fontSize: '20px', fontWeight: 'bold', color: terminado ? 'var(--c-6ee7b7)' : 'var(--c-f8fafc)' }}>
            {Math.floor(pct)} %
          </span>
          <span title={terminado ? 'Tiempo total de la ejecución' : 'Tiempo transcurrido'} style={{ fontSize: '13px', color: 'var(--c-94a3b8)', fontFamily: 'ui-monospace, monospace' }}>
            ⏱ {reloj(total)}
          </span>
        </div>
      </div>
      <div
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.floor(pct)}
        aria-label="Progreso de la ejecución (estimado)"
        style={{ position: 'relative', height: '10px', borderRadius: '999px', backgroundColor: 'var(--c-1e293b)', overflow: 'hidden' }}
      >
        <div
          className={terminado ? undefined : 'barra-franjas'}
          style={{ height: '100%', width: `${pct}%`, borderRadius: '999px', transition: 'width 0.35s ease-out', backgroundColor: terminado ? 'var(--c-34d399)' : 'var(--c-14b8a6)', boxShadow: terminado ? 'none' : '0 0 10px rgba(45, 212, 191, 0.55)' }}
        />
        {/* marcas entre fases */}
        {[TRAMOS[2][0], TRAMOS[3][0]].map((m) => (
          <span key={m} style={{ position: 'absolute', top: 0, bottom: 0, left: `${m}%`, width: '2px', backgroundColor: 'var(--c-020617)', opacity: 0.6 }} />
        ))}
      </div>
    </div>
  );
}
