// Scène « machine » : processeur, mémoire, disque, batterie, processus les plus gourmands,
// courbe des 2 dernières minutes, puce 3D. Lecture seule ; température « indisponible »
// (elle exigerait les droits administrateur : jamais de sudo).

import { cadre, COULEURS, courbe, fr, jauge, ligne, section, tx } from '../dessin.js';
import { trier } from '../registre.js';

export default {
  disposition: 'pleine',
  vivant: true,
  dessiner(c, W, H, ev, ui) {
    const m = ui.vivant || ev.donnees, large = W >= 560, zones = [];
    const nom = m.systeme === 'Darwin' ? 'Mac' : (m.systeme || 'machine');
    const R = cadre(c, W, H, ev.titre, `${nom} · lecture seule · ${m.heure || ''}`);
    const gw = large ? R.w * 0.62 : R.w, gr = large ? Math.min(34, gw / 8) : Math.min(28, gw / 8.4);
    const v = [
      [m.cpu == null ? null : m.cpu / 100, m.cpu == null ? '—' : fr(m.cpu, 0) + '%', 'CPU'],
      [m.ram ? m.ram.pourcent / 100 : null, m.ram ? fr(m.ram.utilisee_go, 0) : '—', 'RAM GO'],
      [m.disque ? m.disque.pourcent / 100 : null, m.disque ? fr(m.disque.pourcent, 0) + '%' : '—', 'DISQUE'],
      [m.batterie ? m.batterie.pourcent / 100 : null, m.batterie ? m.batterie.pourcent + '%' : '—', 'BATTERIE'],
    ];
    v.forEach((x, i) => {
      const cx = R.x + gw * (i + 0.5) / 4, cy = R.y + gr + 6;
      jauge(c, cx, cy, gr, x[0], x[1], x[2]);
      zones.push({ id: 'j' + i, type: 'point', x: cx - gr - 4, y: cy - gr - 4, w: gr * 2 + 8, h: gr * 2 + 24, label: `${x[2]} : ${x[1]}`, info: [x[1], x[2]] });
    });
    const py = R.y + gr * 2 + 44, procs = trier(m.processus || [], ui.tri || 'cpu');
    const rh = large ? 26 : 23, lignes = Math.max(1, Math.min(procs.length, large ? 5 : Math.floor((H - py - 110) / rh)));
    section(c, 'CE QUI L’UTILISE', R.x, py);
    const maxCpu = Math.max(...procs.map((p) => p.cpu), 1);
    procs.slice(0, lignes).forEach((p, i) => {
      const y = py + 22 + i * rh;
      ligne(c, R.x, y, gw - 8, p.nom, fr(p.cpu, 1) + ' %', p.cpu / maxCpu, rh);
      zones.push({ id: 'p' + i, type: 'ligne', x: R.x - 4, y: y - 16, w: gw, h: rh, label: `${p.nom} : ${fr(p.cpu, 1)} % du processeur`,
        info: [p.nom, `processeur ${fr(p.cpu, 1)} % · mémoire ${fr(p.ram, 1)} %`] });
    });
    const hist = (m.historique || []).map((h) => h.cpu);
    let heros = null, sx, sy, sw, sh;
    if (large) {
      sx = R.x + gw + 22; sw = R.w - gw - 22;
      heros = { type: 'puce', x: sx, y: R.y, w: sw, h: Math.min(110, R.h * 0.36) };
      sy = R.y + heros.h + 22; sh = Math.max(40, Math.min(130, R.h - heros.h - 40));
    } else { sx = R.x; sw = R.w; sy = py + 22 + lignes * rh + 6; sh = Math.max(0, R.y + R.h - sy - 8); }
    if (sh >= 30 && hist.length > 1) {
      section(c, 'PROCESSEUR · 2 DERNIÈRES MIN', sx, sy);
      courbe(c, sx, sy + 10, sw, sh - 10, hist, 100).forEach((p, i) => {
        zones.push({ id: 'h' + i, type: 'point', x: p.x - 5, y: sy + 10, w: 10, h: sh - 10, label: `CPU ${fr(p.v || 0, 0)} %`,
          info: [`${fr(p.v || 0, 0)} %`, (m.historique[i] || {}).heure || ''] });
      });
    }
    tx(c, 'Température processeur : indisponible (droits administrateur nécessaires, jamais de sudo).', R.x, R.y + R.h + 12, 9.5, COULEURS.gris2, 400, 'm');
    return { zones, heros };
  },
};
