// Para codigo/tests/test_interfaz.py: lee de la entrada estándar una lista de casos {ruta, pares, criterio} y escribe
// en la salida la ruta recalculada por la pantalla (src/lectura.ts), para compararla con fase3_scoring/nps.py.
// Uso: node pruebas/recalcular.ts < casos.json
import { aplicarCriterio, recalcularRuta, type Criterio, type LecturaRuta, type ParRuta } from '../src/lectura.ts';

interface Caso {
  ruta: LecturaRuta;
  pares: ParRuta[];
  criterio: Record<string, Criterio>;
}

let entrada = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', (trozo) => { entrada += trozo; });
process.stdin.on('end', () => {
  const casos = JSON.parse(entrada) as Caso[];
  const salida = casos.map((c) => recalcularRuta(c.ruta, aplicarCriterio(c.pares, c.criterio)));
  process.stdout.write(JSON.stringify(salida));
});
