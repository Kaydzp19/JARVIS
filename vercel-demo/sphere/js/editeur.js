// Éditeur local : Kayd ouvre une note (action humaine, sur sa machine).
// Une note SENSIBLE n'est jamais ouverte depuis un hologramme : elle reste refusée,
// Kayd l'ouvre lui-même dans le cockpit (/cockpit → Notes).

import { $ } from './outils.js';

export function creerEditeur({ source, surMessage }) {
  const dlg = $('editeur');
  let courant = null, avant = null;

  async function ouvrir(projet, id, { depuisWidget = false } = {}) {
    let n;
    try { n = await source.note(projet, id); } catch (e) { surMessage(`Impossible d’ouvrir la note : ${e.message}`); return false; }
    if (n.sensible && depuisWidget) { surMessage(`« ${n.titre} » est sensible : elle reste fermée ici. Ouvre-la toi-même dans le cockpit.`); return false; }
    courant = n;
    avant = document.activeElement;
    $('editeur-titre').textContent = n.titre;
    $('editeur-meta').textContent = `${n.projet}${n.sensible ? ' · sensible' : ''}${n.demo ? ' · démo' : ''}`
      + (n.liens && n.liens.length ? ` · liens : ${n.liens.map((l) => l.titre).join(', ')}` : '');
    $('editeur-texte').value = n.contenu;
    $('editeur-texte').readOnly = !!n.demo;
    $('editeur-enregistrer').disabled = !!n.demo;
    if (dlg.showModal) dlg.showModal(); else dlg.setAttribute('open', '');
    $('editeur-texte').focus();
    return true;
  }
  function fermer() {
    if (dlg.close) dlg.close(); else dlg.removeAttribute('open');
    courant = null;
    if (avant && avant.focus) avant.focus();
  }
  $('editeur-fermer').addEventListener('click', fermer);
  dlg.addEventListener('close', () => { courant = null; });
  $('editeur-enregistrer').addEventListener('click', async () => {
    if (!courant) return;
    try {
      await source.enregistrerNote(courant.projet, courant.id, $('editeur-texte').value);
      surMessage(`Note « ${courant.titre} » enregistrée.`);
      fermer();
    } catch (e) { surMessage(`Enregistrement impossible : ${e.message}`); }
  });
  return { ouvrir, fermer, get ouvert() { return !!courant; } };
}
