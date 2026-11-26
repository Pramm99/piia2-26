// Rueda de ajustes de la cabecera y panel «token-api»: las claves de Gemini y de Groq que usa la Fase 2, y la clave
// y el correo de NCBI que usa la Fase 1. El puente las guarda en codigo/.env (no se sube a GitHub) y de las claves
// solo devuelve sus primeras y últimas letras.
import React, { useEffect, useRef, useState } from 'react';
import { KeyRound, Loader2, Settings, Trash2, X } from 'lucide-react';
import { mensaje, NOMBRE_PROVEEDOR } from './comun';

export interface ProveedorClaves {
  id: string; // gemini | groq
  modelo: string;
  papel: 'principal' | 'respaldo';
  variable: string;
  claves: string[]; // enmascaradas, en el orden en que se usan
  de_entorno: boolean; // la variable está en el entorno del sistema y manda sobre codigo/.env
}

export interface EstadoNcbi {
  clave: string | null; // enmascarada
  email: string | null;
  clave_de_entorno: boolean;
  email_de_entorno: boolean;
}

// Para qué sirve cada API y dónde se saca la clave (gratis en las tres)
const PARA_QUE: Record<string, { texto: string; enlace: string; sitio: string }> = {
  gemini: {
    texto: 'Fase 2. Es el modelo de lenguaje que lee los abstracts de cada gen y decide qué dicen sobre el gen en la ruta. Sin ninguna clave de Gemini, responde solo Groq.',
    enlace: 'https://aistudio.google.com/apikey',
    sitio: 'aistudio.google.com',
  },
  groq: {
    texto: 'Fase 2, respaldo. Solo responde cuando Gemini falla o se queda sin cupo. Sus claves empiezan por gsk_.',
    enlace: 'https://console.groq.com/keys',
    sitio: 'console.groq.com',
  },
  ncbi: {
    texto: 'Fase 1. De NCBI (PubMed) se descargan los artículos y los abstracts de cada gen. Funciona sin clave; con clave va más rápido (10 peticiones por segundo en vez de 3). El correo es el contacto que NCBI pide a quien usa su servicio.',
    enlace: 'https://www.ncbi.nlm.nih.gov/account/settings/',
    sitio: 'NCBI → Account settings → API Key Management',
  },
};

function ParaQue({ id }: { id: string }) {
  const p = PARA_QUE[id];
  if (!p) return null;
  return (
    <div style={{ fontSize: '11px', color: 'var(--c-94a3b8)', lineHeight: 1.5 }}>
      {p.texto} Clave gratis en{' '}
      <a href={p.enlace} target="_blank" rel="noreferrer" style={{ color: 'var(--c-2dd4bf)' }}>
        {p.sitio}
      </a>
      .
    </div>
  );
}

const campoTexto: React.CSSProperties = {
  flex: '1 1 220px', minWidth: 0, padding: '7px 10px', borderRadius: '8px', border: '1px solid var(--c-334155)',
  backgroundColor: 'var(--c-0f172a)', color: 'var(--c-f8fafc)', fontSize: '12px',
};

const botonMenu: React.CSSProperties = {
  padding: '7px 9px', borderRadius: '8px', border: '1px solid var(--c-334155)', backgroundColor: 'var(--c-1e293b)',
  color: 'var(--c-f8fafc)', fontSize: '12px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px',
};

// Rueda arriba a la derecha con un mini-menú (de momento, una opción: token-api)
export function MenuAjustes({ onTokenApi }: { onTokenApi: () => void }) {
  const [abierto, setAbierto] = useState(false);
  const caja = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!abierto) return;
    const fuera = (e: MouseEvent) => {
      if (caja.current && !caja.current.contains(e.target as Node)) setAbierto(false);
    };
    const escape = (e: KeyboardEvent) => e.key === 'Escape' && setAbierto(false);
    document.addEventListener('mousedown', fuera);
    document.addEventListener('keydown', escape);
    return () => {
      document.removeEventListener('mousedown', fuera);
      document.removeEventListener('keydown', escape);
    };
  }, [abierto]);

  return (
    <div ref={caja} style={{ position: 'relative' }}>
      <button onClick={() => setAbierto(!abierto)} title="Ajustes" aria-label="Ajustes" aria-haspopup="menu" aria-expanded={abierto} style={botonMenu}>
        <Settings size={16} />
      </button>
      {abierto && (
        <div role="menu" style={{ position: 'absolute', right: 0, top: 'calc(100% + 6px)', zIndex: 20, minWidth: '190px', padding: '4px', borderRadius: '10px', border: '1px solid var(--c-334155)', backgroundColor: 'var(--c-0f172a)', boxShadow: '0 10px 30px rgba(0, 0, 0, 0.35)' }}>
          <button
            role="menuitem"
            onClick={() => {
              setAbierto(false);
              onTokenApi();
            }}
            style={{ width: '100%', padding: '8px 10px', borderRadius: '7px', border: 'none', background: 'none', color: 'var(--c-f8fafc)', fontSize: '13px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '8px', textAlign: 'left' }}
          >
            <KeyRound size={15} color="var(--c-2dd4bf)" />
            <span>token-api</span>
          </button>
        </div>
      )}
    </div>
  );
}

// Panel para añadir y quitar claves. Cada cambio se guarda al momento y vale desde la siguiente ejecución.
export function PanelTokens({ api, onCerrar }: { api: string; onCerrar: () => void }) {
  const [proveedores, setProveedores] = useState<ProveedorClaves[] | null>(null);
  const [ncbi, setNcbi] = useState<EstadoNcbi | null>(null);
  const [nuevas, setNuevas] = useState<Record<string, string>>({});
  const [ocupado, setOcupado] = useState<string | null>(null); // proveedor con una petición en curso
  const [porQuitar, setPorQuitar] = useState<string | null>(null); // «proveedor:indice» a la espera de confirmar
  const [error, setError] = useState<string | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const res = await fetch(`${api}/claves`);
        const d = await res.json();
        if (!res.ok || !d.ok) throw new Error(d.error || 'El puente no devolvió las claves');
        setProveedores(d.proveedores);
        setNcbi(d.ncbi || null);
      } catch (err) {
        setError(`No se pudieron leer las claves: ${mensaje(err)}. ¿Está en marcha api_puente.py?`);
      }
    })();
    const escape = (e: KeyboardEvent) => e.key === 'Escape' && onCerrar();
    document.addEventListener('keydown', escape);
    return () => document.removeEventListener('keydown', escape);
  }, [api, onCerrar]);

  const cambiar = async (proveedor: string, cuerpo: Record<string, unknown>, hecho: string) => {
    setOcupado(proveedor);
    setError(null);
    setAviso(null);
    try {
      const res = await fetch(`${api}/claves`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ proveedor, ...cuerpo }),
      });
      const d = await res.json();
      if (!res.ok || !d.ok) throw new Error(d.error || 'No se pudo guardar');
      setProveedores(d.proveedores);
      setNcbi(d.ncbi || null);
      setAviso(d.ejecutando ? `${hecho} Hay una ruta en marcha: el cambio vale desde la siguiente ejecución.` : hecho);
      return true;
    } catch (err) {
      setError(mensaje(err));
      return false;
    } finally {
      setOcupado(null);
      setPorQuitar(null);
    }
  };

  const anadir = async (p: ProveedorClaves) => {
    const clave = (nuevas[p.id] || '').trim();
    if (!clave) return;
    if (await cambiar(p.id, { accion: 'anadir', clave }, `Clave de ${NOMBRE_PROVEEDOR[p.id] || p.id} añadida.`)) {
      setNuevas((n) => ({ ...n, [p.id]: '' }));
    }
  };

  // NCBI: una sola clave y un correo; guardar sustituye el que hubiera
  const guardarNcbi = async (campo: 'clave' | 'email') => {
    const id = `ncbi-${campo}`;
    const valor = (nuevas[id] || '').trim();
    if (!valor) return;
    if (await cambiar('ncbi', { accion: 'guardar', campo, valor }, campo === 'clave' ? 'Clave de NCBI guardada.' : 'Correo de NCBI guardado.')) {
      setNuevas((n) => ({ ...n, [id]: '' }));
    }
  };

  const filaNcbi = (campo: 'clave' | 'email') => {
    if (!ncbi) return null;
    const id = `ncbi-${campo}`;
    const actual = campo === 'clave' ? ncbi.clave : ncbi.email;
    const deEntorno = campo === 'clave' ? ncbi.clave_de_entorno : ncbi.email_de_entorno;
    const variable = campo === 'clave' ? 'NCBI_API_KEY' : 'NCBI_EMAIL';
    const bloqueado = deEntorno || ocupado !== null;
    const escrito = (nuevas[id] || '').trim();
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
        <div style={{ fontSize: '12px', display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
          <span style={{ color: 'var(--c-94a3b8)' }}>{campo === 'clave' ? 'Clave' : 'Correo'}:</span>
          {actual ? <code style={{ color: 'var(--c-e2e8f0)' }}>{actual}</code> : <span style={{ color: 'var(--c-fbbf24)' }}>{campo === 'clave' ? 'sin clave (va a 3 peticiones por segundo)' : 'sin correo'}</span>}
          {actual && !deEntorno && (porQuitar === id ? (
            <>
              <button disabled={bloqueado} onClick={() => cambiar('ncbi', { accion: 'quitar', campo }, campo === 'clave' ? 'Clave de NCBI quitada.' : 'Correo de NCBI quitado.')} style={{ ...botonMenu, padding: '2px 8px', fontSize: '11px', color: 'var(--c-fda4af)' }}>
                Sí, quitarlo
              </button>
              <button onClick={() => setPorQuitar(null)} style={{ ...botonMenu, padding: '2px 8px', fontSize: '11px' }}>
                No
              </button>
            </>
          ) : (
            <button disabled={bloqueado} onClick={() => setPorQuitar(id)} title={campo === 'clave' ? 'Quitar la clave' : 'Quitar el correo'} aria-label={campo === 'clave' ? 'Quitar la clave de NCBI' : 'Quitar el correo de NCBI'} style={{ ...botonMenu, padding: '2px 6px', color: 'var(--c-fda4af)', opacity: bloqueado ? 0.5 : 1 }}>
              <Trash2 size={12} />
            </button>
          ))}
        </div>
        {deEntorno && (
          <div style={{ fontSize: '11px', color: 'var(--c-fbbf24)' }}>
            {variable} está en las variables de entorno del sistema, que mandan sobre codigo/.env: quítala de ahí para cambiarla desde aquí.
          </div>
        )}
        <form
          onSubmit={(e) => {
            e.preventDefault();
            guardarNcbi(campo);
          }}
          style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}
        >
          <input
            type={campo === 'clave' ? 'password' : 'email'}
            autoComplete="off"
            spellCheck={false}
            disabled={bloqueado}
            value={nuevas[id] || ''}
            onChange={(e) => setNuevas((n) => ({ ...n, [id]: e.target.value }))}
            placeholder={campo === 'clave' ? 'Pega la clave de NCBI (36 caracteres)' : 'Tu correo de contacto'}
            aria-label={campo === 'clave' ? 'Clave de NCBI' : 'Correo de NCBI'}
            style={campoTexto}
          />
          <button type="submit" disabled={bloqueado || !escrito} style={{ ...botonMenu, opacity: bloqueado || !escrito ? 0.5 : 1 }}>
            {ocupado === 'ncbi' ? <Loader2 size={14} className="animate-spin" /> : null}
            {actual ? 'Cambiar' : 'Guardar'}
          </button>
        </form>
      </div>
    );
  };

  return (
    <div onMouseDown={(e) => e.target === e.currentTarget && onCerrar()} style={{ position: 'fixed', inset: 0, zIndex: 50, backgroundColor: 'rgba(2, 6, 23, 0.6)', display: 'flex', alignItems: 'flex-start', justifyContent: 'center', padding: '60px 16px', overflowY: 'auto' }}>
      <div role="dialog" aria-modal="true" aria-label="token-api" style={{ width: '100%', maxWidth: '620px', borderRadius: '14px', border: '1px solid var(--c-334155)', backgroundColor: 'var(--c-0f172a)', color: 'var(--c-f8fafc)', padding: '20px', boxSizing: 'border-box', display: 'flex', flexDirection: 'column', gap: '14px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '12px' }}>
          <span style={{ fontSize: '16px', fontWeight: 'bold', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <KeyRound size={18} color="var(--c-2dd4bf)" /> token-api
          </span>
          <button onClick={onCerrar} aria-label="Cerrar" style={{ ...botonMenu, padding: '5px' }}>
            <X size={15} />
          </button>
        </div>

        <div style={{ fontSize: '12px', color: 'var(--c-94a3b8)', lineHeight: 1.5 }}>
          Aquí van las claves de las tres APIs que usa el análisis. Para preguntar al modelo de lenguaje hace falta al menos una de <strong>Gemini</strong> (el principal) o de <strong>Groq</strong> (el respaldo); la de <strong>NCBI</strong> es opcional. De Gemini y de Groq puedes poner varias; se usan en el orden de la lista.
          <ul style={{ margin: '6px 0 0', paddingLeft: '18px', listStyle: 'disc' }}>
            <li>Si una clave de Gemini se queda sin su cupo diario, se pasa a la <strong>siguiente clave de Gemini</strong>.</li>
            <li>Si Gemini falla por otro motivo (clave no válida, servicio o red caídos) o se acaban todas sus claves, responde <strong>Groq</strong>, que también usa sus claves en orden.</li>
            <li>Si no queda ninguna con cupo, las preguntas quedan pendientes y se avisa: añade la clave de otra cuenta o espera al día siguiente.</li>
          </ul>
          Se guardan en <code>codigo/.env</code> de este equipo (no se suben a GitHub) y valen desde la siguiente ejecución. Aquí solo se ven sus primeras y últimas letras.
        </div>

        {error && <div style={{ fontSize: '12px', color: 'var(--c-fda4af)', padding: '8px 10px', borderRadius: '8px', border: '1px solid var(--c-be123c)', backgroundColor: 'rgba(225, 29, 72, 0.12)' }}>{error}</div>}
        {aviso && <div style={{ fontSize: '12px', color: 'var(--c-5eead4)', padding: '8px 10px', borderRadius: '8px', border: '1px solid var(--c-0f766e)', backgroundColor: 'rgba(20, 184, 166, 0.1)' }}>{aviso}</div>}

        {!proveedores && !error && (
          <div style={{ fontSize: '12px', color: 'var(--c-94a3b8)', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Loader2 size={14} className="animate-spin" /> Leyendo las claves…
          </div>
        )}

        {proveedores?.map((p) => {
          const nombre = NOMBRE_PROVEEDOR[p.id] || p.id;
          const bloqueado = p.de_entorno || ocupado !== null;
          return (
            <section key={p.id} style={{ borderRadius: '10px', border: '1px solid var(--c-1e293b)', backgroundColor: 'var(--c-020617)', padding: '12px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'baseline', gap: '6px' }}>
                <span style={{ fontSize: '14px', fontWeight: 'bold' }}>{nombre}</span>
                <span style={{ fontSize: '11px', color: 'var(--c-94a3b8)' }}>
                  {p.papel === 'principal' ? 'principal' : 'respaldo'} · {p.modelo}
                </span>
              </div>
              <ParaQue id={p.id} />
              {p.de_entorno && (
                <div style={{ fontSize: '11px', color: 'var(--c-fbbf24)' }}>
                  {p.variable} está en las variables de entorno del sistema, que mandan sobre codigo/.env: quítala de ahí para gestionar estas claves desde aquí.
                </div>
              )}
              {p.claves.length === 0 ? (
                <div style={{ fontSize: '12px', color: 'var(--c-fbbf24)' }}>Sin ninguna clave: {p.papel === 'principal' ? 'responderá solo Groq.' : 'si Gemini falla, no habrá respaldo.'}</div>
              ) : (
                <ol style={{ margin: 0, paddingLeft: '22px', listStyle: 'decimal', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                  {p.claves.map((c, i) => {
                    const id = `${p.id}:${i}`;
                    return (
                      <li key={id} style={{ fontSize: '12px' }}>
                        <span style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                          <code style={{ color: 'var(--c-e2e8f0)' }}>{c}</code>
                          {i === 0 && <span style={{ fontSize: '10px', color: 'var(--c-64748b)' }}>se usa primero</span>}
                          {porQuitar === id ? (
                            <>
                              <button disabled={bloqueado} onClick={() => cambiar(p.id, { accion: 'quitar', indice: i }, `Clave ${i + 1} de ${nombre} quitada.`)} style={{ ...botonMenu, padding: '2px 8px', fontSize: '11px', color: 'var(--c-fda4af)' }}>
                                Sí, quitarla
                              </button>
                              <button onClick={() => setPorQuitar(null)} style={{ ...botonMenu, padding: '2px 8px', fontSize: '11px' }}>
                                No
                              </button>
                            </>
                          ) : (
                            <button disabled={bloqueado} onClick={() => setPorQuitar(id)} title="Quitar esta clave" aria-label={`Quitar la clave ${i + 1} de ${nombre}`} style={{ ...botonMenu, padding: '2px 6px', color: 'var(--c-fda4af)', opacity: bloqueado ? 0.5 : 1 }}>
                              <Trash2 size={12} />
                            </button>
                          )}
                        </span>
                      </li>
                    );
                  })}
                </ol>
              )}
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  anadir(p);
                }}
                style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}
              >
                <input
                  type="password"
                  autoComplete="off"
                  spellCheck={false}
                  disabled={bloqueado}
                  value={nuevas[p.id] || ''}
                  onChange={(e) => setNuevas((n) => ({ ...n, [p.id]: e.target.value }))}
                  placeholder={`Pega una clave de ${nombre}${p.id === 'groq' ? ' (gsk_…)' : ''}`}
                  aria-label={`Nueva clave de ${nombre}`}
                  style={campoTexto}
                />
                <button type="submit" disabled={bloqueado || !(nuevas[p.id] || '').trim()} style={{ ...botonMenu, opacity: bloqueado || !(nuevas[p.id] || '').trim() ? 0.5 : 1 }}>
                  {ocupado === p.id ? <Loader2 size={14} className="animate-spin" /> : null}
                  Añadir
                </button>
              </form>
            </section>
          );
        })}

        {ncbi && (
          <section style={{ borderRadius: '10px', border: '1px solid var(--c-1e293b)', backgroundColor: 'var(--c-020617)', padding: '12px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
            <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'baseline', gap: '6px' }}>
              <span style={{ fontSize: '14px', fontWeight: 'bold' }}>NCBI</span>
              <span style={{ fontSize: '11px', color: 'var(--c-94a3b8)' }}>opcional · PubMed</span>
            </div>
            <ParaQue id="ncbi" />
            {filaNcbi('clave')}
            {filaNcbi('email')}
          </section>
        )}
      </div>
    </div>
  );
}
