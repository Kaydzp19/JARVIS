// Scène « résumé de la nuit » : synapses renforcées, archivées, idées en attente,
// dépense du mois (barres 3D), et les 4 phases. Rien n'est écrit sans validation.

import { cadre, COULEURS, fr, tx } from '../dessin.js';

export default {
  disposition: 'pleine',
  dessiner(c, W, H, ev) {
    const d = ev.donnees, large = W >= 560, zones = [];
    const R = cadre(c, W, H, ev.titre, d.date ? `nuit du ${d.date}` : 'pas encore de nuit');
    const grands = [
      [d.renforcees, 'renforcées', COULEURS.bleu],
      [d.archivees, 'archivées', '#fff'],
      [d.propositions_en_attente ?? d.idees_en_attente ?? 0, 'à valider', COULEURS.jaune],
      [d.depense_mois == null ? '—' : fr(d.depense_mois, 2) + ' €', `dépense / ${fr(d.plafond || 0, 0)} €`, COULEURS.texte],
    ];
    const bw = (large ? R.w * 0.64 : R.w) / 4;
    grands.forEach((g, i) => {
      const x = R.x + bw * i;
      tx(c, String(g[0]), x, R.y + (large ? 46 : 40), large ? (i === 3 ? 30 : 46) : (i === 3 ? 20 : 34), g[2], 700);
      tx(c, g[1], x, R.y + (large ? 64 : 56), large ? 9.5 : 8, COULEURS.gris, 500, 'm');
      zones.push({ id: 'g' + i, type: 'point', x: x - 4, y: R.y + 4, w: bw - 4, h: 66, label: `${g[1]} : ${g[0]}`, info: [String(g[0]), g[1]] });
    });
    const phases = ['Tri : oubli de 2 %, apprentissage +0,10, archivage sous 0,05',
      'Analyse : chaque projet relu, séparément', 'Rêve : notes éloignées rapprochées',
      'Réveil : la meilleure idée gardée, à valider'];
    const y0 = R.y + (large ? 100 : 86), rh = Math.max(22, Math.min(44, (R.y + R.h - y0 - 10) / 4));
    phases.forEach((p, i) => {
      const y = y0 + i * rh;
      c.fillStyle = COULEURS.bleu; c.shadowColor = COULEURS.bleu; c.shadowBlur = 7; c.beginPath(); c.arc(R.x + 6, y - 5, 3.5, 0, 7); c.fill(); c.shadowBlur = 0;
      if (i < 3) { c.strokeStyle = 'rgba(110,200,255,0.3)'; c.beginPath(); c.moveTo(R.x + 6, y); c.lineTo(R.x + 6, y + rh - 10); c.stroke(); }
      tx(c, p, R.x + 22, y, large ? 14 : 12, COULEURS.texte2, 500);
      tx(c, d.date ? 'fait' : '—', R.x + R.w, y, 10, COULEURS.gris, 400, 'm', 'right');
    });
    tx(c, 'Rien n’est écrit dans la mémoire sans ta validation (garde d’écriture).', R.x, R.y + R.h + 12, 9.5, COULEURS.gris2, 400, 'm');
    const valeurs = [d.renforcees || 0, d.archivees || 0, grands[2][0] || 0, d.depense_mois || 0];
    return { zones, heros: large ? { type: 'barres', x: R.x + R.w * 0.68, y: R.y - 2, w: R.w * 0.32, h: 84, valeurs,
      max: Math.max(...valeurs, 1), couleurs: [0x4CC9FF, 0xFFFFFF, 0xFFD84A, 0x8FE0FF] } : null };
  },
};
