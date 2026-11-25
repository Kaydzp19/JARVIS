// Scène « graphique » : barres 3D (ou courbe), plafond, période modifiable.
// Changer de période demande de nouvelles données à JARVIS (affichage.action) ;
// le widget se met à jour sur place.

import { cadre, COULEURS, courbe, fr, tx } from '../dessin.js';

export default {
  disposition: 'pleine',
  dessiner(c, W, H, ev, ui) {
    const d = ev.donnees, serie = d.serie || [], unite = d.unite ? ' ' + d.unite : '';
    const sous = [d.periode, d.plafond != null ? `plafond ${fr(d.plafond, 0)}${unite}` : null].filter(Boolean).join(' · ');
    const R = cadre(c, W, H, ev.titre, sous);
    const zones = [];
    if (!serie.length) { tx(c, 'Aucune donnée pour cette période.', R.x, R.y + 26, 14, COULEURS.gris, 500); return { zones }; }
    const valeurs = serie.map((s) => Number(s.valeur) || 0);
    const max = Math.max(...valeurs, d.plafond || 0, 1e-9) * 1.05;
    const bas = R.y + R.h - 30, haut = R.y + 14, n = serie.length, pas = R.w / n;
    const dec = d.unite === '€' ? 2 : 0;
    c.strokeStyle = 'rgba(110,200,255,0.12)'; c.lineWidth = 1;
    for (let g = 0; g < 4; g++) { const gy = haut + (bas - haut) * g / 4; c.beginPath(); c.moveTo(R.x, gy); c.lineTo(R.x + R.w, gy); c.stroke(); }
    if (d.plafond) {
      const py = bas - (bas - haut) * d.plafond / max;
      c.setLineDash([5, 5]); c.strokeStyle = 'rgba(255,216,74,0.7)'; c.beginPath(); c.moveTo(R.x, py); c.lineTo(R.x + R.w, py); c.stroke(); c.setLineDash([]);
      tx(c, `plafond ${fr(d.plafond, 0)}${unite}`, R.x + R.w, py - 5, 10, COULEURS.jaune, 500, 'm', 'right');
    }
    const saut = Math.ceil(n / Math.max(1, Math.floor(R.w / 46)));
    serie.forEach((s, i) => {
      const cx = R.x + pas * (i + 0.5);
      if (i % saut === 0 || i === n - 1) {
        tx(c, s.etiquette, cx, bas + 14, 10, COULEURS.gris, 500, 'm', 'center');
        if (n <= 12) tx(c, fr(valeurs[i], dec) + unite, cx, bas + 30, W < 420 ? 11 : 14, i === n - 1 ? '#fff' : '#B8D8F0', 700, 'd', 'center');
      }
      const hauteur = Math.max(6, (bas - haut) * valeurs[i] / max);
      zones.push({ id: 'b' + i, type: 'barre', x: cx - pas / 2, y: bas - hauteur - 8, w: pas, h: hauteur + 44,
        label: `${s.etiquette} : ${fr(valeurs[i], dec)}${unite}`, info: [`${fr(valeurs[i], dec)}${unite}`, s.etiquette] });
    });
    if (d.type === 'ligne') {
      courbe(c, R.x + pas / 2, haut, R.w - pas, bas - haut, valeurs, max);
      return { zones };
    }
    return { zones, heros: { type: 'barres', x: R.x, y: haut, w: R.w, h: bas - haut, valeurs, max, incline: true } };
  },
};
