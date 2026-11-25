// Widget générique : pour une scène que l'interface ne connaît pas encore.
// Jamais d'erreur à l'écran : un tableau (liste d'objets), un graphique simple
// (liste de nombres ou série), sinon les valeurs simples de l'événement.

import { cadre, COULEURS, couper, fr, tx } from '../dessin.js';

function trouverTableau(v, profondeur = 0) {
  if (Array.isArray(v) && v.length && v.every((x) => x && typeof x === 'object' && !Array.isArray(x))) return v;
  if (v && typeof v === 'object' && profondeur < 3) for (const x of Object.values(v)) { const t = trouverTableau(x, profondeur + 1); if (t) return t; }
  return null;
}
function trouverNombres(v, profondeur = 0) {
  if (Array.isArray(v) && v.length && v.every((x) => typeof x === 'number')) return v.map((x, i) => ({ etiquette: String(i + 1), valeur: x }));
  if (v && typeof v === 'object' && profondeur < 3) for (const x of Object.values(v)) { const t = trouverNombres(x, profondeur + 1); if (t) return t; }
  return null;
}
const simple = (x) => x == null || ['string', 'number', 'boolean'].includes(typeof x);
const texte = (x) => (typeof x === 'number' ? fr(x, Number.isInteger(x) ? 0 : 2) : x == null ? '—' : String(x));

export default {
  disposition: 'pleine',
  dessiner(c, W, H, ev) {
    const R = cadre(c, W, H, ev.titre, `scène « ${ev.scene} » · vue générique`), zones = [];
    const d = ev.donnees || {};
    const serie = Array.isArray(d.serie) && d.serie.every((s) => s && typeof s.valeur === 'number') ? d.serie : null;
    const table = serie ? null : trouverTableau(d);
    if (table) {
      const cols = Object.keys(table[0]).filter((k) => simple(table[0][k])).slice(0, 4), cw = R.w / Math.max(1, cols.length);
      cols.forEach((k, j) => tx(c, k.toUpperCase(), R.x + j * cw, R.y + 12, 9.5, COULEURS.gris, 500, 'm'));
      const rh = 26, n = Math.min(table.length, Math.floor((R.h - 24) / rh));
      table.slice(0, n).forEach((ligne, i) => {
        const y = R.y + 38 + i * rh;
        cols.forEach((k, j) => { c.font = '500 14px Rajdhani'; tx(c, couper(c, texte(ligne[k]), cw - 10), R.x + j * cw, y, 14, COULEURS.texte2, 500); });
        zones.push({ id: 'l' + i, type: 'ligne', x: R.x - 4, y: y - 17, w: R.w + 8, h: rh - 2, label: cols.map((k) => `${k} ${texte(ligne[k])}`).join(', '),
          info: [texte(ligne[cols[0]]), cols.slice(1).map((k) => `${k} ${texte(ligne[k])}`).join(' · ')] });
      });
      return { zones };
    }
    const nombres = serie || trouverNombres(d);
    if (nombres) {
      const max = Math.max(...nombres.map((s) => s.valeur), 1e-9), bas = R.y + R.h - 20, pas = R.w / nombres.length;
      nombres.forEach((s, i) => {
        const h = (bas - R.y - 10) * s.valeur / max, x = R.x + pas * i + pas * 0.2;
        c.fillStyle = 'rgba(76,201,255,0.55)'; c.fillRect(x, bas - h, pas * 0.6, h);
        tx(c, s.etiquette, x + pas * 0.3, bas + 14, 9.5, COULEURS.gris, 500, 'm', 'center');
        zones.push({ id: 'b' + i, type: 'barre', x: R.x + pas * i, y: bas - h - 4, w: pas, h: h + 24, label: `${s.etiquette} : ${texte(s.valeur)}`, info: [texte(s.valeur), s.etiquette] });
      });
      return { zones };
    }
    Object.entries(d).filter(([, v]) => simple(v)).slice(0, Math.floor(R.h / 24)).forEach(([k, v], i) => {
      tx(c, k, R.x, R.y + 18 + i * 24, 12, COULEURS.gris, 500, 'm');
      tx(c, texte(v), R.x + R.w, R.y + 18 + i * 24, 15, COULEURS.texte2, 600, 'd', 'right');
    });
    return { zones };
  },
};
