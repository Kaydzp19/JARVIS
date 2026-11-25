// Planification : logique pure (récurrence, validation, données d'affichage), même règles
// que noyau/planification.py. Sert au mode DÉMO (aucun serveur). Testée dans Node.

export const PRIORITES = ['basse', 'normale', 'haute'];
export const RECURRENCES = ['aucune', 'quotidienne', 'jours_ouvres', 'hebdomadaire', 'mensuelle'];
export const CHAMPS = ['titre', 'date', 'heure', 'duree', 'priorite', 'recurrence', 'rappel', 'note_id'];

/** Date « AAAA-MM-JJ » <-> objet (à midi UTC, pour éviter les décalages d'heure d'été). */
export const versDate = (s) => new Date(String(s).slice(0, 10) + 'T12:00:00Z');
export const versTexte = (d) => d.toISOString().slice(0, 10);
export const plusJours = (s, n) => { const d = versDate(s); d.setUTCDate(d.getUTCDate() + n); return versTexte(d); };
const joursDuMois = (a, m) => new Date(Date.UTC(a, m + 1, 0)).getUTCDate();
const jourSemaine = (s) => (versDate(s).getUTCDay() + 6) % 7;      // lundi = 0

/** Les dates successives d'une tâche récurrente à partir de son ancrage (générateur). */
export function* suite(ancre, recurrence) {
  if (recurrence === 'aucune') { yield ancre; return; }
  if (recurrence === 'mensuelle') {
    const d = versDate(ancre), jour = d.getUTCDate();
    for (let n = 0; ; n++) {
      const m = d.getUTCMonth() + n, a = d.getUTCFullYear() + Math.floor(m / 12), mm = ((m % 12) + 12) % 12;
      yield versTexte(new Date(Date.UTC(a, mm, Math.min(jour, joursDuMois(a, mm)), 12)));
    }
  }
  const pas = recurrence === 'hebdomadaire' ? 7 : 1;
  for (let d = ancre; ; d = plusJours(d, pas)) {
    if (recurrence !== 'jours_ouvres' || jourSemaine(d) < 5) yield d;
  }
}

export function prochaineDate(courante, recurrence, ancre = null) {
  if (recurrence === 'aucune') return null;
  for (const d of suite(ancre || courante, recurrence)) if (d > courante) return d;
  return null;
}

/** Dates de la tâche entre debut et fin inclus, à partir de sa date actuelle. */
export function occurrences(t, debut, fin, maximum = 62) {
  if (!t.echeance) return [];
  const r = t.echeance >= debut && t.echeance <= fin ? [t.echeance] : [];
  for (const d of suite(t.ancre || t.echeance, t.recurrence || 'aucune')) {
    if (d > fin || r.length >= maximum) break;
    if (d > t.echeance && d >= debut) r.push(d);
  }
  return r;
}

/** Valide et nettoie des champs ; lève une erreur lisible sinon. */
export function validerChamps(champs, { partiel = false, notes = null } = {}) {
  const e = (m) => { throw new Error(m); };
  const inconnus = Object.keys(champs).filter((k) => !CHAMPS.includes(k));
  if (inconnus.length) e('Champs inconnus : ' + inconnus.join(', '));
  const p = {};
  if ('titre' in champs || !partiel) {
    const t = String(champs.titre || '').trim();
    if (!t || t.length > 120) e('Le titre est obligatoire (120 caractères au plus).');
    p.titre = t;
  }
  if ('date' in champs) {
    const d = champs.date || null;
    if (d && !/^\d{4}-\d{2}-\d{2}$/.test(d)) e('Date attendue au format AAAA-MM-JJ.');
    p.echeance = d;
  }
  if ('heure' in champs) {
    const h = champs.heure || null;
    if (h && !/^([01]\d|2[0-3]):[0-5]\d$/.test(h)) e('Heure attendue au format HH:MM.');
    p.heure = h;
  }
  if ('duree' in champs || !partiel) {
    const d = parseInt(champs.duree || 30, 10);
    if (!(d >= 5 && d <= 1440)) e('Durée entre 5 minutes et 24 heures.');
    p.duree = d;
  }
  if ('priorite' in champs || !partiel) {
    const v = champs.priorite || 'normale';
    if (!PRIORITES.includes(v)) e('Priorité inconnue.');
    p.priorite = v;
  }
  if ('recurrence' in champs || !partiel) {
    const v = champs.recurrence || 'aucune';
    if (!RECURRENCES.includes(v)) e('Récurrence inconnue.');
    p.recurrence = v;
  }
  if ('rappel' in champs) {
    const v = champs.rappel === '' || champs.rappel == null ? null : parseInt(champs.rappel, 10);
    if (v != null && !(v >= 0 && v <= 10080)) e('Rappel entre 0 minute et 7 jours avant.');
    p.rappel = v;
  }
  if ('note_id' in champs) {
    const v = champs.note_id === '' || champs.note_id == null ? null : Number(champs.note_id);
    if (v != null && notes && !notes.some((n) => n.id === v)) e('La note liée doit appartenir au même projet.');
    p.note_id = v;
  }
  if ((p.recurrence || 'aucune') !== 'aucune' && !p.echeance && (!partiel || 'echeance' in p)) e('Une tâche récurrente a besoin d’une date.');
  return p;
}

/** Lundi de la semaine d'une date. */
export const lundi = (s) => plusJours(s, -jourSemaine(s));

/** Les tâches d'une période (occurrences comprises) pour des projets { nom: [taches] }. */
export function lister(parProjet, projet, debut, jours, titresNotes = {}) {
  const fin = plusJours(debut, Math.max(1, jours) - 1), taches = [], sansDate = [];
  const noms = projet === '*' ? Object.keys(parProjet) : [projet];
  noms.forEach((p) => (parProjet[p] || []).forEach((t) => {
    const sortie = (d, occ) => ({ id: t.id, projet: p, titre: t.titre, statut: t.statut, date: d, heure: t.heure || null,
      duree: t.duree || 30, priorite: t.priorite || 'normale', recurrence: t.recurrence || 'aucune', rappel: t.rappel ?? null,
      note_id: t.note_id ?? null, note_titre: (titresNotes[p] || {})[t.note_id] || null, planifiee: false, occurrence: occ });
    if (!t.echeance) { sansDate.push(sortie(null, false)); return; }
    occurrences(t, debut, fin).forEach((d, i) => taches.push(sortie(d, i > 0 || d > t.echeance)));
  }));
  taches.sort((a, b) => (a.date + (a.heure || '99:99') + a.projet).localeCompare(b.date + (b.heure || '99:99') + b.projet) || a.id - b.id);
  return { taches, sans_date: sansDate };
}

/** Libellés lisibles. */
export const JOURS = ['lun.', 'mar.', 'mer.', 'jeu.', 'ven.', 'sam.', 'dim.'];
export const MOIS = ['janv.', 'févr.', 'mars', 'avr.', 'mai', 'juin', 'juil.', 'août', 'sept.', 'oct.', 'nov.', 'déc.'];
export function libelleDate(s) {
  const d = versDate(s);
  return `${JOURS[jourSemaine(s)]} ${d.getUTCDate()} ${MOIS[d.getUTCMonth()]}`;
}
export const LIBELLES_RECURRENCE = { aucune: 'une fois', quotidienne: 'chaque jour', jours_ouvres: 'jours ouvrés',
  hebdomadaire: 'chaque semaine', mensuelle: 'chaque mois' };
