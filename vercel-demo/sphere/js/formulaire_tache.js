// La fiche d'une tâche : créer, modifier, Fait / Pas fait, supprimer.
// Ce sont des ACTIONS HUMAINES de Kayd : enregistrées directement (et journalisées).
// Une tâche proposée par JARVIS, elle, passe par « À valider » (jamais par cette fiche).

import { $, el } from './outils.js';

export function creerFormulaireTache({ source, projets, notesDe, apres, annoncer }) {
  const dlg = $('tache'), f = (id) => $('tache-' + id);
  let courant = null, avant = null, confirmer = false;
  projets.forEach((p) => { const o = el('option', '', p); o.value = p; f('projet').appendChild(o); });

  function remplirNotes(projet, choisie) {
    const s = f('note');
    s.textContent = '';
    const aucune = el('option', '', 'aucune'); aucune.value = ''; s.appendChild(aucune);
    (notesDe(projet) || []).forEach((n) => { const o = el('option', '', n.titre); o.value = n.id; s.appendChild(o); });
    s.value = choisie == null ? '' : String(choisie);
  }
  f('projet').addEventListener('change', () => remplirNotes(f('projet').value, null));

  /** ouvrir({ projet, tache }) pour modifier, ou ouvrir({ projet, date, heure }) pour créer. */
  function ouvrir({ projet, tache = null, date = '', heure = '' }) {
    courant = { projet, tache };
    avant = document.activeElement;
    confirmer = false;
    const t = tache || {};
    f('entete').textContent = tache ? 'Modifier la tâche' : 'Nouvelle tâche';
    f('meta').textContent = tache
      ? `${projet}${t.recurrence && t.recurrence !== 'aucune' ? ' · tâche récurrente : les changements valent pour toute la série' : ''}${t.statut && t.statut !== 'à faire' ? ' · ' + t.statut : ''}`
      : 'Créée par toi : enregistrée tout de suite, notée au journal.';
    f('titre').value = t.titre || '';
    f('date').value = t.date || date || '';
    f('heure').value = t.heure || heure || '';
    f('duree').value = String(t.duree || 30);
    if (!f('duree').value) f('duree').value = '30';
    f('projet').value = projet; f('projet').disabled = !!tache;
    f('priorite').value = t.priorite || 'normale';
    f('recurrence').value = t.recurrence || 'aucune';
    f('rappel').value = t.rappel == null ? '' : String(t.rappel);
    remplirNotes(projet, t.note_id);
    ['supprimer', 'fait', 'pasfait'].forEach((b) => { f(b).hidden = !tache; });
    f('supprimer').textContent = 'Supprimer'; f('supprimer').classList.remove('danger');
    f('erreur').textContent = '';
    if (dlg.showModal) dlg.showModal(); else dlg.setAttribute('open', '');
    f('titre').focus();
  }
  function fermer() {
    if (dlg.close) dlg.close(); else dlg.removeAttribute('open');
    courant = null;
    if (avant && avant.focus && document.contains(avant)) avant.focus();
  }
  async function faire(action, options, message) {
    const projet = courant.tache ? courant.tache.projet || courant.projet : f('projet').value;
    try {
      const r = await source.taches(action, projet, options);
      if (annoncer) annoncer(message);
      fermer();
      await apres({ action, projet, resultat: r });
    } catch (e) { f('erreur').textContent = e.message; }
  }
  const champs = () => ({ titre: f('titre').value.trim(), date: f('date').value || null, heure: f('heure').value || null,
    duree: Number(f('duree').value), priorite: f('priorite').value, recurrence: f('recurrence').value,
    rappel: f('rappel').value === '' ? null : Number(f('rappel').value),
    note_id: f('note').value === '' ? null : Number(f('note').value) });

  $('tache-form').addEventListener('submit', (e) => {
    e.preventDefault();
    if (!f('titre').value.trim()) { f('erreur').textContent = 'Le titre est obligatoire.'; f('titre').focus(); return; }
    if (courant.tache) faire('modifier', { id: courant.tache.id, champs: champs() }, 'Tâche modifiée.');
    else faire('creer', { champs: champs() }, 'Tâche créée.');
  });
  f('annuler').addEventListener('click', fermer);
  f('fait').addEventListener('click', () => faire('terminer', { id: courant.tache.id, fait: true }, 'Tâche marquée faite.'));
  f('pasfait').addEventListener('click', () => faire('terminer', { id: courant.tache.id, fait: false }, 'Tâche marquée pas faite.'));
  f('supprimer').addEventListener('click', () => {
    if (!confirmer) { confirmer = true; f('supprimer').textContent = 'Confirmer la suppression'; f('supprimer').classList.add('danger'); return; }
    faire('supprimer', { id: courant.tache.id }, 'Tâche supprimée.');
  });
  dlg.addEventListener('close', () => { courant = null; });
  return { ouvrir, fermer, get ouvert() { return !!courant; } };
}
