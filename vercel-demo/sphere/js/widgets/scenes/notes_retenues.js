// Scène « notes retenues » : titres et scores seulement (jamais le texte des notes).
// Cliquer une note l'allume sur la sphère ; « Ouvrir la note » ouvre l'éditeur local.

import { cadre, COULEURS, couper, fr, rr, tx } from '../dessin.js';
import { filtrer, trier } from '../registre.js';

export default {
  disposition: 'pleine',
  filtreTexte: true,
  dessiner(c, W, H, ev, ui) {
    const tous = ev.projet === '*';
    const R = cadre(c, W, H, ev.titre, (tous ? 'tous les projets · lecture seule' : ev.projet || '') + ' · titres seulement');
    const notes = filtrer(trier(ev.donnees.notes || [], ui.tri || 'rang'), ui.filtre || '');
    const zones = [];
    if (!notes.length) { tx(c, 'Aucune note ne correspond.', R.x, R.y + 26, 14, COULEURS.gris, 500); return { zones }; }
    const max = Math.max(...notes.map((n) => n.score || 0), 1e-9);
    const cols = W >= 560 && notes.length > 4 ? 2 : 1, cw = R.w / cols, rh = Math.max(26, Math.min(36, R.h / Math.ceil(notes.length / cols)));
    const parCol = Math.max(1, Math.floor(R.h / rh)), visibles = notes.slice(0, parCol * cols);
    visibles.forEach((n, i) => {
      const col = Math.floor(i / parCol), ri = i % parCol, x = R.x + col * cw, y = R.y + 10 + ri * rh, w = cw - (cols > 1 ? 22 : 0);
      const choisie = ui.selection === `n:${n.projet}:${n.id}`;
      if (choisie) { c.fillStyle = 'rgba(255,138,61,0.12)'; rr(c, x - 6, y - 4, w + 12, rh - 4, 5); c.fill(); }
      tx(c, (n.rang < 10 ? '0' : '') + n.rang, x, y + 14, 11, COULEURS.orange, 600, 'm');
      c.font = '600 15px Rajdhani';
      const etq = n.sensible ? ' · sensible' : (tous ? ' · ' + n.projet : '');
      tx(c, couper(c, n.titre, w - 110) , x + 28, y + 14, 15, n.sensible ? COULEURS.jaune : '#FFB07A', 600);
      if (etq) { const lt = c.measureText(couper(c, n.titre, w - 110)).width; tx(c, etq, x + 34 + lt, y + 14, 9.5, n.sensible ? COULEURS.jaune : COULEURS.gris2, 400, 'm'); }
      tx(c, fr(n.score || 0, 2), x + w, y + 14, 11, COULEURS.gris, 400, 'm', 'right');
      c.fillStyle = 'rgba(255,138,61,0.18)'; c.fillRect(x + 28, y + 19, w - 28, 2);
      c.fillStyle = 'rgba(255,138,61,0.85)'; c.fillRect(x + 28, y + 19, (w - 28) * (n.score || 0) / max, 2);
      zones.push({ id: `n:${n.projet}:${n.id}`, type: 'note', x: x - 6, y: y - 4, w: w + 12, h: rh - 4,
        label: `Note ${n.rang} : ${n.titre}${n.sensible ? ' (sensible)' : ''}`,
        info: [n.titre, `${n.projet} · score ${fr(n.score || 0, 2)}${n.sensible ? ' · sensible' : ''}`],
        note: { projet: n.projet, id: n.id, sensible: !!n.sensible } });
    });
    if (notes.length > visibles.length) tx(c, `+ ${notes.length - visibles.length} autres (agrandis le widget)`, R.x, R.y + R.h + 12, 9.5, COULEURS.gris2, 400, 'm');
    return { zones };
  },
};
