// Scène « météo » : température, courbe des 24 heures, 7 jours, soleil et nuage 3D.

import { cadre, COULEURS, courbe, fr, rr, section, tx } from '../dessin.js';

export function ciel(code) {
  if (code == null) return 'inconnu';
  if (code === 0) return 'ciel clair';
  if (code <= 3) return 'nuageux';
  if (code <= 48) return 'brouillard';
  if (code <= 67) return 'pluie';
  if (code <= 77) return 'neige';
  if (code <= 82) return 'averses';
  return 'orage';
}
const pluvieux = (code) => code != null && code >= 51 && code < 95;

export default {
  disposition: (ev) => (ev.donnees.disponible ? 'pleine' : 'carte'),
  dessiner(c, W, H, ev) {
    const d = ev.donnees, large = W >= 560, zones = [];
    const R = cadre(c, W, H, ev.titre, d.disponible ? `${d.lieu ? d.lieu + ' · ' : ''}${d.lieu === 'Paris' ? 'données fictives' : 'Open-Meteo'}` : 'indisponible');
    if (!d.disponible) {
      tx(c, 'Météo indisponible', R.x, R.y + 30, 22, COULEURS.jaune, 700);
      tx(c, d.raison || '', R.x, R.y + 56, 11, COULEURS.gris, 400, 'm');
      return { zones };
    }
    const t = d.actuelle || {};
    tx(c, t.temperature == null ? '—' : fr(t.temperature, 0) + '°', R.x, R.y + (large ? 58 : 44), large ? 66 : 50, '#fff', 700);
    tx(c, ciel(t.code), R.x + (large ? 112 : 84), R.y + (large ? 30 : 22), large ? 19 : 15, COULEURS.texte2, 600);
    const pluie = (d.heures || []).some((h) => (h.pluie || 0) >= 50);
    tx(c, pluie ? 'Pluie probable dans les 24 h' : 'Pas de pluie prévue', R.x + (large ? 112 : 84), R.y + (large ? 54 : 42), large ? 15 : 13, COULEURS.gris, 500);
    const cy = R.y + (large ? 80 : 64), ch = Math.max(40, Math.min(100, R.h - (large ? 80 : 64) - (large ? 92 : 70)));
    section(c, 'PROCHAINES 24 HEURES', R.x, cy);
    const temps = (d.heures || []).map((h) => h.temperature);
    const mn = Math.min(...temps, 0), mx = Math.max(...temps, 1);
    courbe(c, R.x, cy + 10, R.w, ch, temps.map((v) => v - mn), (mx - mn) || 1).forEach((p, i) => {
      const h = d.heures[i];
      zones.push({ id: 'h' + i, type: 'point', x: p.x - R.w / 48, y: cy + 10, w: R.w / 24, h: ch, label: `${h.heure} : ${fr(h.temperature, 0)} degrés`,
        info: [`${fr(h.temperature, 0)} °C`, `${h.heure} · pluie ${h.pluie == null ? '—' : h.pluie + ' %'}`] });
    });
    const jours = d.jours || [], dy = R.y + R.h - (large ? 56 : 44), cw = R.w / Math.max(1, jours.length);
    jours.forEach((j, i) => {
      const x = R.x + cw * i + 2, bw = cw - 6, bh = large ? 54 : 42;
      c.strokeStyle = 'rgba(110,200,255,0.2)'; c.lineWidth = 1; rr(c, x, dy, bw, bh, 7); c.stroke();
      const nom = /^\d{4}-/.test(j.date) ? new Date(j.date + 'T12:00').toLocaleDateString('fr-FR', { weekday: 'short' }).replace('.', '') : j.date;
      tx(c, nom.toUpperCase(), x + bw / 2, dy + 14, 9.5, COULEURS.gris, 500, 'm', 'center');
      tx(c, fr(j.max, 0) + '°', x + bw / 2, dy + (large ? 36 : 33), large ? 19 : 15, '#fff', 700, 'd', 'center');
      if (large) tx(c, ciel(j.code), x + bw / 2, dy + 49, 8.5, COULEURS.gris2, 400, 'm', 'center');
      zones.push({ id: 'j' + i, type: 'point', x, y: dy, w: bw, h: bh, label: `${nom} : ${fr(j.max, 0)} degrés, ${ciel(j.code)}`,
        info: [`${nom} · ${ciel(j.code)}`, `min ${fr(j.min, 0)}° · max ${fr(j.max, 0)}°`] });
    });
    return { zones, heros: large ? { type: 'meteo', x: R.x + R.w - 160, y: R.y + 6, w: 150, h: 70, pluie: pluvieux(t.code) || pluie } : null };
  },
};
