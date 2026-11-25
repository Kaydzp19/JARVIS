// Contrat d'affichage côté interface : la même validation que noyau/affichage.py.
// Un événement invalide n'est jamais affiché tel quel ; une scène inconnue
// est affichée par le widget générique (jamais d'erreur à l'écran).

export const MOTIF_SCENE = /^[a-z][a-z0-9_]{0,39}$/;
export const MOTIF_ACTION = /^[a-z][a-z0-9_]{0,39}$/;
export const CLES_INTERDITES = new Set(['contenu', 'texte', 'extrait', 'corps']);
export const CONTROLES = new Set(['onglets', 'filtres', 'tri', 'periode']);
export const PERIODES = ['24 h', '7 j', '30 j', '6 mois', '12 mois'];
export const VERBES_ECRITURE = ['ecrire', 'creer', 'modifier', 'supprimer', 'effacer', 'publier',
  'payer', 'acheter', 'envoyer', 'valider', 'refuser', 'archiver'];
export const PROJET_TRANSVERSAL = '*';
const CHAMPS = new Set(['scene', 'titre', 'donnees', 'projet', 'controles', 'actions', 'id',
  'version', 'cree_le', 'maj_le', 'fermeture']);
const TAILLE_MAX = 64000;

function clesInterdites(v, chemin = 'donnees') {
  let t = [];
  if (Array.isArray(v)) v.forEach((x, i) => { t = t.concat(clesInterdites(x, `${chemin}[${i}]`)); });
  else if (v && typeof v === 'object') {
    for (const [k, x] of Object.entries(v)) {
      if (CLES_INTERDITES.has(String(k).toLowerCase())) t.push(`${chemin}.${k}`);
      t = t.concat(clesInterdites(x, `${chemin}.${k}`));
    }
  }
  return t;
}

/** Vrai si l'action écrit, supprime, publie ou paie (type déclaré OU nom). */
export function estEcriture(action) {
  const nom = typeof action === 'object' && action ? String(action.id || '') : String(action);
  if (action && typeof action === 'object' && action.type === 'ecriture') return true;
  return VERBES_ECRITURE.some((v) => nom === v || nom.startsWith(v + '_'));
}

const estTexte = (x) => typeof x === 'string';
const estObjet = (x) => x && typeof x === 'object' && !Array.isArray(x);

/** Renvoie la liste des erreurs (vide si l'événement est valide). */
export function valider(ev) {
  const e = [];
  if (!estObjet(ev)) return ["l'événement doit être un objet"];
  const inconnus = Object.keys(ev).filter((k) => !CHAMPS.has(k)).sort();
  if (inconnus.length) e.push('champs inconnus : ' + inconnus.join(', '));
  if (!estTexte(ev.scene) || !MOTIF_SCENE.test(ev.scene)) e.push('scene : identifiant attendu (minuscules, chiffres, _)');
  if (!estTexte(ev.titre) || !ev.titre.trim() || ev.titre.length > 120) e.push('titre : texte de 1 à 120 caractères');
  if (!estObjet(ev.donnees)) e.push('donnees : objet attendu');
  else {
    clesInterdites(ev.donnees).forEach((c) => e.push(`${c} : le texte des notes n'est jamais envoyé à l'interface`));
    if (JSON.stringify(ev.donnees).length > TAILLE_MAX) e.push('donnees : trop volumineuses');
  }
  if (ev.projet != null && (!estTexte(ev.projet) || !ev.projet.trim())) e.push('projet : nom de projet ou absent');
  if ('fermeture' in ev && !(typeof ev.fermeture === 'number' && ev.fermeture >= 0 && ev.fermeture <= 600))
    e.push('fermeture : nombre de secondes entre 0 et 600 (0 = reste ouvert)');
  const c = ev.controles == null ? {} : ev.controles;
  if (!estObjet(c)) e.push('controles : objet attendu');
  else for (const [k, v] of Object.entries(c)) {
    if (!CONTROLES.has(k)) e.push(`controles.${k} : contrôle inconnu`);
    else if (!(Array.isArray(v) && v.length && v.every((x) => estTexte(x) && x))) e.push(`controles.${k} : liste de textes attendue`);
    else if (k === 'periode' && v.some((x) => !PERIODES.includes(x))) e.push('controles.periode : valeurs permises ' + PERIODES.join(', '));
  }
  const a = ev.actions == null ? [] : ev.actions;
  if (!Array.isArray(a)) e.push('actions : liste attendue');
  else {
    const vus = new Set();
    a.forEach((x, i) => {
      if (!estObjet(x) || !MOTIF_ACTION.test(String(x.id || ''))) { e.push(`actions[${i}] : id attendu`); return; }
      if (vus.has(x.id)) e.push(`actions[${i}] : id en double`);
      vus.add(x.id);
      if (!estTexte(x.libelle) || !x.libelle.trim()) e.push(`actions[${i}] : libelle attendu`);
      if (!['lecture', 'ecriture'].includes(x.type || 'lecture')) e.push(`actions[${i}] : type lecture ou ecriture`);
      if (ev.projet === PROJET_TRANSVERSAL && estEcriture(x)) e.push(`actions[${i}] : la vue « tous les projets » est en lecture seule`);
    });
  }
  return e;
}

/** Valeurs par défaut (comme _normaliser en Python). */
export function normaliser(ev) {
  return {
    ...ev,
    titre: ev.titre.trim(),
    projet: ev.projet == null ? null : ev.projet,
    controles: { ...(ev.controles || {}) },
    actions: (ev.actions || []).map((x) => ({ ...x, type: estEcriture(x) ? 'ecriture' : (x.type || 'lecture') })),
  };
}

export const SCENES_CONNUES = ['notes_retenues', 'graphique', 'machine', 'meteo', 'resume_nuit', 'note_privee', 'planification'];
export const sceneConnue = (s) => SCENES_CONNUES.includes(s);
