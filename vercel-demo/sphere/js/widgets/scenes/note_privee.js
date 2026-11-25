// Scène « note sensible refusée » : cadenas 3D, « contenu privé, N caractères ».
// Le contenu n'est jamais affiché par JARVIS ; Kayd peut l'ouvrir lui-même dans l'éditeur local.

import { cadre, COULEURS, couper, tx } from '../dessin.js';

export default {
  disposition: 'carte',
  dessiner(c, W, H, ev) {
    const d = ev.donnees, large = W >= 560, R = cadre(c, W, H, ev.titre, 'accès refusé à l’affichage');
    const x = R.x + (large ? 96 : 70);
    tx(c, `contenu privé, ${d.caracteres ?? '?'} caractères`, x, R.y + 26, large ? 24 : 17, COULEURS.jaune, 700);
    c.font = '500 14px Rajdhani';
    tx(c, couper(c, `« ${d.titre} » ne s’ouvre que dans l’éditeur local, par toi.`, R.w - (x - R.x)), x, R.y + 48, large ? 14 : 12, COULEURS.gris, 500);
    tx(c, 'JARVIS n’affiche jamais le contenu des notes sensibles.', x, R.y + 66, 10, COULEURS.gris2, 400, 'm');
    return { zones: [], heros: { type: 'cadenas', x: R.x, y: R.y - 4, w: large ? 84 : 62, h: large ? 84 : 62 } };
  },
};
