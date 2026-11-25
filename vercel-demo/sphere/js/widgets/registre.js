// Registre des hologrammes : applique les événements d'affichage (sans dessiner).
// Un seul hologramme à la fois. Logique pure, testée dans Node.
//
//   appliquer(ev) -> { geste: 'ouvrir' | 'mettre_a_jour' | 'ignorer' | 'refuser', ev, erreurs, generique }
//   fermer()      -> l'événement fermé (ou null)

import { normaliser, sceneConnue, valider } from './contrat.js';

export function creerRegistre() {
  let courant = null;
  return {
    get courant() { return courant; },
    appliquer(brut) {
      const erreurs = valider(brut);
      if (erreurs.length) return { geste: 'refuser', ev: null, erreurs, generique: false };
      const ev = normaliser(brut);
      ev.version = ev.version || 1;
      const generique = !sceneConnue(ev.scene);
      if (courant && ev.id != null && courant.id === ev.id) {
        if (ev.version <= courant.version) return { geste: 'ignorer', ev: courant, erreurs: [], generique };
        courant = ev;
        return { geste: 'mettre_a_jour', ev, erreurs: [], generique };
      }
      courant = ev;
      return { geste: 'ouvrir', ev, erreurs: [], generique };
    },
    fermer() { const f = courant; courant = null; return f; },
  };
}

/** Durée d'affichage avant fermeture automatique (secondes ; 0 = reste ouvert). */
export function dureeAffichage(ev) {
  if (typeof ev.fermeture === 'number') return ev.fermeture;
  return ev.scene === 'note_privee' ? 14 : 28;
}

/** Tri local d'une liste d'objets (sans appel serveur). */
export function trier(liste, cle) {
  const l = liste.slice();
  if (cle === 'titre' || cle === 'nom') l.sort((a, b) => String(a[cle]).localeCompare(String(b[cle]), 'fr'));
  else if (cle === 'rang') l.sort((a, b) => (a.rang || 0) - (b.rang || 0));
  else l.sort((a, b) => (b[cle] || 0) - (a[cle] || 0));
  return l;
}

/** Filtre local par texte (titre ou nom), sans accents. */
export function filtrer(liste, texte) {
  const n = (s) => String(s || '').toLowerCase().normalize('NFD').replace(/\p{M}/gu, '');
  const q = n(texte).trim();
  return q ? liste.filter((x) => n(x.titre || x.nom || x.etiquette).includes(q)) : liste;
}
