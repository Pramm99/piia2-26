// Logo de la cabecera: el mismo dibujo que el icono del programa y de la pestaña (codigo/empaquetado/icono.svg; si
// cambia uno, cambia el otro). Va en el código como SVG: nítido con cualquier escalado y sin descargar nada.
export default function Logo({ size = 40 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" role="img" aria-label="PathwayPulse" style={{ flexShrink: 0 }}>
      <rect x="0.5" y="0.5" width="23" height="23" rx="5.5" fill="#14b8a6" />
      <g fill="none" stroke="#020617" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
        <rect x="7" y="3.6" width="4.6" height="8.4" rx="1.2" fill="#020617" strokeWidth="1.2" />
        <path d="M13.6 8.4a5.6 5.6 0 0 1 0 11.2" />
        <path d="M6.4 15.6h6" />
        <path d="M4.4 19.6h15.2" />
      </g>
    </svg>
  );
}
