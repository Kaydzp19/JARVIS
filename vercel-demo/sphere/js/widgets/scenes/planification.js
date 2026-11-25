// Scène « planification » : les prochaines tâches de Kayd.
//   liste    les tâches de la période, par date (et celles sans date)
//   jour     une frise horaire (7 h → 22 h)
//   semaine  sept frises, une par jour (du lundi au dimanche)
// Les rendez-vous de l'agenda Apple (module) sont en violet, non modifiables.
// Cliquer une tâche ouvre sa fiche (et allume sa note dans la sphère) ; la glisser la
// déplace (jour, heure). « ＋ Tâche » en crée une. Vue « tous les projets » : lecture seule.

import { cadre, COULEURS, couper, rr, section, tx } from '../dessin.js';
import { LIBELLES_RECURRENCE, libelleDate, plusJours } from '../../planification.js';

const H0 = 7, H1 = 22;
export const VIOLET = '#B79CFF';
const minutes = (h) => { const [a, b] = String(h).split(':').map(Number); return a * 60 + b; };
const hhmm = (m) => `${String(Math.floor(m / 60)).padStart(2, '0')}:${String(m % 60).padStart(2, '0')}`;

function couleurTache(t) {
  if (t.statut === 'fait') return { fond: 'rgba(143,169,194,0.14)', bord: 'rgba(143,169,194,0.45)', texte: COULEURS.gris2 };
  if (t.statut === 'pas fait') return { fond: 'rgba(143,169,194,0.08)', bord: 'rgba(143,169,194,0.6)', texte: COULEURS.gris, tirets: true };
  const haute = t.priorite === 'haute';
  return { fond: t.occurrence ? 'rgba(76,201,255,0.10)' : 'rgba(76,201,255,0.22)', bord: haute ? '#FFFFFF' : COULEURS.bleu,
    texte: COULEURS.texte, tirets: t.occurrence };
}

function detail(t) {
  return [t.date ? libelleDate(t.date) : 'sans date', t.heure ? `${t.heure} · ${t.duree} min` : `${t.duree} min`,
    t.priorite !== 'normale' ? `priorité ${t.priorite}` : null, t.recurrence !== 'aucune' ? LIBELLES_RECURRENCE[t.recurrence] : null,
    t.rappel != null ? `rappel ${t.rappel} min avant` : null, t.note_titre ? `note : ${t.note_titre}` : null,
    t.statut !== 'à faire' ? t.statut : null].filter(Boolean).join(' · ');
}

function zoneTache(t, x, y, w, h, deplacable, tous) {
  return { id: `t:${t.projet}:${t.id}:${t.date}`, type: 'tache', x, y, w, h, tache: t, deplacable,
    label: `Tâche : ${t.titre}, ${detail(t)}${tous ? ', ' + t.projet : ''}`,
    info: [t.titre + (tous ? ` · ${t.projet}` : ''), detail(t)] };
}

function zoneExterne(e, i, x, y, w, h) {
  return { id: `e${i}:${e.debut}`, type: 'externe', x, y, w, h,
    label: `Agenda Apple : ${e.titre}, ${e.debut.slice(11, 16)} à ${e.fin.slice(11, 16)} (lecture seule)`,
    info: [e.titre, `${e.calendrier ? e.calendrier + ' · ' : ''}${e.debut.slice(11, 16)}–${e.fin.slice(11, 16)} · agenda Apple, lecture seule`] };
}

function bloc(c, x, y, w, h, coul, titre, taille = 12) {
  c.fillStyle = coul.fond; rr(c, x, y, Math.max(6, w), h, 4); c.fill();
  c.strokeStyle = coul.bord; c.lineWidth = 1.2;
  if (coul.tirets) c.setLineDash([4, 3]);
  rr(c, x + 0.5, y + 0.5, Math.max(5, w - 1), h - 1, 4); c.stroke(); c.setLineDash([]);
  if (w > 24) {
    c.font = `600 ${taille}px Rajdhani`;
    tx(c, couper(c, titre, w - 8), x + 5, y + h / 2 + taille * 0.36, taille, coul.texte, 600);
  }
}

function axe(c, x0, x1, y, bas) {
  for (let h = H0; h <= H1; h += 1) {
    const x = x0 + (x1 - x0) * (h - H0) / (H1 - H0);
    c.strokeStyle = h % 2 ? 'rgba(110,200,255,0.05)' : 'rgba(110,200,255,0.12)';
    c.beginPath(); c.moveTo(x, y + 6); c.lineTo(x, bas); c.stroke();
    if (h % 2 === 1 || h === H1) continue;
    tx(c, `${h} h`, x, y, 9, COULEURS.gris2, 500, 'm', 'center');
  }
}

const xDe = (g, m) => g.x0 + (g.x1 - g.x0) * (Math.max(H0 * 60, Math.min(H1 * 60, m)) - H0 * 60) / ((H1 - H0) * 60);

/** Place les blocs d'une journée dans des couloirs, sans chevauchement (largeur affichée comprise). */
function couloirs(taches, minimum = 0) {
  const fins = [];
  return taches.map((t) => {
    const debut = minutes(t.heure), fin = debut + Math.max(t.duree, minimum);
    let k = fins.findIndex((f) => f <= debut);
    if (k < 0) { k = fins.length; fins.push(fin); } else fins[k] = fin;
    return { t, k };
  });
}

function frise(c, g, ligne, taches, externes, ro, tous, zones, hauteurExt) {
  const { y, h, date } = ligne;
  externes.filter((e) => e.debut.slice(0, 10) === date && !e.journee).forEach((e, i) => {
    const x = xDe(g, minutes(e.debut.slice(11, 16))), w = Math.max(6, xDe(g, minutes(e.fin.slice(11, 16))) - x);
    bloc(c, x, y + 2, w, hauteurExt, { fond: 'rgba(183,156,255,0.18)', bord: VIOLET, texte: '#E5DBFF' }, e.titre, 10.5);
    zones.push(zoneExterne(e, zones.length + i, x, y + 2, w, hauteurExt));
  });
  const jour = taches.filter((t) => t.date === date);
  const avecHeure = jour.filter((t) => t.heure).sort((a, b) => a.heure.localeCompare(b.heure));
  const parMinute = (g.x1 - g.x0) / ((H1 - H0) * 60), largeurMin = 54;
  const places = couloirs(avecHeure, largeurMin / parMinute), nb = Math.max(1, ...places.map((p) => p.k + 1));
  const haut = y + hauteurExt + 5, dispo = h - hauteurExt - 7, hl = Math.min(28, dispo / nb);
  places.forEach(({ t, k }) => {
    const x = xDe(g, minutes(t.heure)), w = Math.max(largeurMin, xDe(g, minutes(t.heure) + t.duree) - x), yy = haut + k * hl;
    bloc(c, x, yy, w, hl - 2, couleurTache(t), t.titre, Math.min(12.5, hl * 0.55));
    zones.push(zoneTache(t, x, yy, w, hl - 2, !ro && !t.occurrence, tous));
  });
  jour.filter((t) => !t.heure).forEach((t, i) => {     // sans heure : petites pastilles au début
    const x = g.x0 - 30, yy = haut + i * 12;
    if (yy + 10 > y + h) return;
    bloc(c, x, yy, 26, 10, couleurTache(t), '', 8);
    zones.push(zoneTache(t, x, yy, 26, 10, !ro && !t.occurrence, tous));
  });
}

export default {
  disposition: 'pleine',
  ongletsServeur: true,
  filtresServeur: true,
  uiDepuis(ev) {
    return { onglet: ev.donnees.vue, filtreChoix: ev.donnees.projet === '*' ? 'tous' : ev.donnees.projet };
  },
  boutons(ev) { return ev.donnees.lecture_seule ? [] : [{ id: 'ajouter', libelle: '＋ Tâche' }]; },

  dessiner(c, W, H, ev) {
    const d = ev.donnees, ro = !!d.lecture_seule, tous = d.projet === '*';
    const fin = plusJours(d.debut, d.jours - 1);
    const periode = d.jours === 1 ? libelleDate(d.debut) : `${libelleDate(d.debut)} → ${libelleDate(fin)}`;
    const C = cadre(c, W, H, ev.titre, `${tous ? 'tous les projets · lecture seule' : d.projet} · ${periode}`, W >= 560 ? 50 : 84);
    const R = { x: C.x, y: C.y + 14, w: C.w, h: C.h - 14 };
    const zones = [], ext = d.externes || {}, externes = ext.disponible ? ext.evenements || [] : [];
    // légende : agenda Apple
    const leg = ext.disponible ? `● agenda Apple (${ext.source || 'Mac'})${ext.masque ? ' · titres masqués' : ''} · lecture seule`
      : (ext.raison || 'Agenda non branché');
    c.font = '400 9.5px "JetBrains Mono"';
    tx(c, couper(c, leg, R.w), R.x + R.w, C.y + 6, 9.5, ext.disponible ? VIOLET : COULEURS.gris2, 400, 'm', 'right');

    if (d.vue === 'liste') {
      const lignes = [];
      let dernier = null;
      d.taches.forEach((t) => { if (t.date !== dernier) { lignes.push({ titre: libelleDate(t.date), aujourd: t.date === d.aujourd_hui }); dernier = t.date; } lignes.push({ t }); });
      if (d.sans_date && d.sans_date.length) { lignes.push({ titre: 'Sans date' }); d.sans_date.forEach((t) => lignes.push({ t })); }
      if (!lignes.length) tx(c, ro ? 'Aucune tâche sur cette période.' : 'Aucune tâche sur cette période. « ＋ Tâche » pour en ajouter une.', R.x, R.y + 24, 14, COULEURS.gris, 500);
      const rh = 24, max = Math.floor((R.h - 4) / rh);
      lignes.slice(0, max).forEach((l, i) => {
        const y = R.y + 4 + i * rh;
        if (l.titre) { section(c, l.titre.toUpperCase() + (l.aujourd ? ' · AUJOURD’HUI' : ''), R.x, y + 15); return; }
        const t = l.t, coul = couleurTache(t);
        c.fillStyle = coul.bord; c.fillRect(R.x, y + 5, 3, rh - 9);
        tx(c, t.heure || '—', R.x + 10, y + 16, 11, COULEURS.gris, 500, 'm');
        c.font = '600 14px Rajdhani';
        const titre = couper(c, (t.statut === 'fait' ? '✓ ' : t.statut === 'pas fait' ? '✕ ' : '') + t.titre, R.w * 0.5);
        tx(c, titre, R.x + 58, y + 16, 14, coul.texte, 600);
        const etq = [tous ? t.projet : null, t.recurrence !== 'aucune' ? '↻ ' + LIBELLES_RECURRENCE[t.recurrence] : null,
          t.note_titre ? '◆ ' + t.note_titre : null, `${t.duree} min`].filter(Boolean).join(' · ');
        c.font = '400 10px "JetBrains Mono"';
        tx(c, couper(c, etq, R.w * 0.42), R.x + R.w, y + 16, 10, COULEURS.gris2, 400, 'm', 'right');
        zones.push(zoneTache(t, R.x - 4, y + 2, R.w + 8, rh - 3, false, tous));
      });
      if (lignes.length > max) tx(c, `+ ${lignes.length - max} lignes (agrandis le widget)`, R.x, C.y + 6, 9.5, COULEURS.gris2, 400, 'm');
      return { zones, geom: null };
    }

    const gauche = d.vue === 'semaine' ? 72 : 34;
    const g = { vue: d.vue, x0: R.x + gauche, x1: R.x + R.w - 6, lignes: [] };
    axe(c, g.x0, g.x1, R.y + 9, R.y + R.h);
    const n = d.vue === 'semaine' ? 7 : 1, y0 = R.y + 16, hLigne = (R.h - 18) / n;
    for (let i = 0; i < n; i++) {
      const date = plusJours(d.debut, i), y = y0 + i * hLigne;
      if (date === d.aujourd_hui) { c.fillStyle = 'rgba(76,201,255,0.06)'; c.fillRect(R.x, y, R.w, hLigne - 2); }
      c.strokeStyle = 'rgba(110,200,255,0.10)'; c.beginPath(); c.moveTo(R.x, y + hLigne - 1); c.lineTo(R.x + R.w, y + hLigne - 1); c.stroke();
      if (d.vue === 'semaine') {
        tx(c, libelleDate(date).replace(/ \S+$/, ''), R.x, y + hLigne / 2 + 4, 12, date === d.aujourd_hui ? COULEURS.texte : COULEURS.gris, 600);
      }
      // ligne « maintenant »
      if (date === d.aujourd_hui) {
        const mt = new Date(), m = mt.getHours() * 60 + mt.getMinutes();
        if (m >= H0 * 60 && m <= H1 * 60) { const x = xDe(g, m); c.strokeStyle = 'rgba(241,248,255,0.55)'; c.beginPath(); c.moveTo(x, y); c.lineTo(x, y + hLigne - 2); c.stroke(); }
      }
      const ligne = { date, y, h: hLigne - 2 };
      g.lignes.push(ligne);
      frise(c, g, ligne, d.taches, externes, ro, tous, zones, d.vue === 'semaine' ? Math.min(12, hLigne * 0.28) : 22);
    }
    return { zones, geom: g };
  },

  /** Une tâche lâchée en (x, y) : nouvelle date et heure (au quart d'heure), ou null. */
  deposer(z, x, y, ev, ui, g) {
    if (!g || !z.tache || ev.donnees.lecture_seule) return null;
    const ligne = g.lignes.find((l) => y >= l.y && y <= l.y + l.h + 2) || (g.lignes.length === 1 ? g.lignes[0] : null);
    if (!ligne) return null;
    let m = H0 * 60 + (x - g.x0) / (g.x1 - g.x0) * (H1 - H0) * 60 - (z.tache.heure ? z.tache.duree / 2 : 0);
    m = Math.round(m / 15) * 15;
    m = Math.max(H0 * 60, Math.min(H1 * 60 - 15, m));
    const r = { date: ligne.date, heure: hhmm(m) };
    return r.date === z.tache.date && r.heure === z.tache.heure ? null : r;
  },
};
