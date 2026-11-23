import { defineConfig, type Plugin } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// Al compilar (npm run build), el index.html no enlaza el JS y el CSS: los pide un cargador con un tiempo límite y
// reintentos. En el equipo de pruebas (con Avast), una descarga del servidor local se queda a veces colgada ~19 s y
// acaba cortada (ERR_CONNECTION_RESET), más cuanto más grande (el JS, 7 de cada 15 veces), y con un <script> normal la
// ventana se quedaba en blanco. En desarrollo (npm run dev) no cambia nada.
function cargaConReintentos(): Plugin {
  return {
    name: 'carga-con-reintentos',
    apply: 'build',
    enforce: 'post',
    transformIndexHtml(html) {
      const js = html.match(/<script type="module" crossorigin src="([^"]+)"><\/script>/);
      const css = html.match(/<link rel="stylesheet" crossorigin href="([^"]+)">/);
      if (!js || !css) throw new Error('carga-con-reintentos: no encuentro el <script> o el <link> de Vite en index.html');
      const cargador = `<script type="module">
      const traer = async (url) => {
        for (let i = 0; i < 8; i++) {
          try {
            const r = await fetch(url, { cache: i ? 'reload' : 'default', signal: AbortSignal.timeout(3000) });
            if (r.ok) return await r.text();
          } catch { /* colgada o cortada: otra vez */ }
        }
        throw new Error(url);
      };
      try {
        const [css, js] = await Promise.all([traer(${JSON.stringify(css[1])}), traer(${JSON.stringify(js[1])})]);
        const estilo = document.createElement('style');
        estilo.textContent = css;
        document.head.append(estilo);
        await import(URL.createObjectURL(new Blob([js], { type: 'text/javascript' })));
      } catch {
        document.getElementById('root').innerHTML = '<p style="font-family:system-ui;color:#94a3b8;padding:24px">' +
          'No se pudo cargar la interfaz. Cierra la ventana y vuelve a abrir el programa.</p>';
      }
    </script>`;
      return html.replace(js[0], cargador).replace(css[0], '');
    },
  };
}

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    cargaConReintentos(),
  ],
  // Un solo fichero JS: el cargador lo importa desde un Blob, sin dirección propia para importar otros trozos
  build: { rollupOptions: { output: { inlineDynamicImports: true } } },
})
