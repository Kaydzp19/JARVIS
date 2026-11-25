// Source de données RÉELLE : le serveur local de JARVIS (interface/serveur_web.py).
// L'interface ne fait que lire et transmettre : toute décision reste côté noyau ou humaine.

import { creerSourceDemo } from './donnees_demo.js';

async function appel(chemin, corps) {
  const r = await fetch(chemin, corps === undefined ? { credentials: 'same-origin' } : {
    method: 'POST', credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(corps),
  });
  let d = null;
  try { d = await r.json(); } catch (e) { /* réponse vide */ }
  if (!r.ok) throw new Error((d && d.erreur) || `Erreur ${r.status}`);
  return d;
}

export function creerSourceReelle() {
  return {
    mode: 'reel',
    peutSimulerNuit: false,          // mis à jour d'après les projets (démo seulement)
    sphere: () => appel('/api/sphere'),
    demander: (texte, projet) => appel('/api/demander', { texte, projet }),
    action: (widget, action, params) => appel('/api/affichage/action', { widget, action, params }),
    systeme: () => appel('/api/systeme'),
    depenses: () => appel('/api/depenses'),
    aValider: () => appel('/api/a_valider'),
    decider: (projet, id, oui) => appel('/api/proposition', { projet, id, action: oui ? 'valider' : 'refuser' }),
    /** ACTIONS HUMAINES sur les tâches : creer, modifier, supprimer, terminer. */
    taches: (action, projet, { id, champs, fait } = {}) => appel('/api/taches', { action, projet, id, champs, fait }),
    prochaines: (nombre = 3) => appel(`/api/prochaines?nombre=${nombre}`),
    ouvrirPlanification: (projet, debut, vue) => appel('/api/planification/ouvrir', { projet, debut, vue }),
    journalDuJour: () => appel('/api/journal_du_jour'),
    note: (projet, id) => appel(`/api/note?projet=${encodeURIComponent(projet)}&id=${encodeURIComponent(id)}`),
    enregistrerNote: (projet, id, contenu) => appel('/api/note', { projet, id, contenu }),
    /** Nuit simulée : seulement pour les projets de DÉMO (le serveur refuse les autres). */
    async simulerNuit(projets) {
      const avant = await appel('/api/sphere');
      const resultats = [];
      for (const p of projets) resultats.push(await appel('/api/nuit', { projet: p }));
      const apres = await appel('/api/sphere');
      return comparerNuit(avant, apres, projets, resultats);
    },
  };
}

/** Bilan d'une nuit à partir de l'état avant / après (pour l'animation). */
export function comparerNuit(avant, apres, projets, resultats = []) {
  const bilan = { projets: [], renforcees: [], archivees: [], propositions: [] };
  const cle = (s) => Math.min(s.a, s.b) + ':' + Math.max(s.a, s.b);
  projets.forEach((nom, i) => {
    const a = avant.projets.find((p) => p.nom === nom), b = apres.projets.find((p) => p.nom === nom);
    if (!a || !b) return;
    const apresPoids = new Map(b.synapses.map((s) => [cle(s), s.poids]));
    let renf = 0, arch = 0;
    a.synapses.forEach((s) => {
      if (!apresPoids.has(cle(s))) { bilan.archivees.push({ projet: nom, a: s.a, b: s.b }); arch++; }
      else if (apresPoids.get(cle(s)) > s.poids + 1e-9) { bilan.renforcees.push({ projet: nom, a: s.a, b: s.b }); renf++; }
    });
    const connues = new Set(a.propositions.map((p) => p.id));
    b.propositions.filter((p) => !connues.has(p.id)).forEach((p) => bilan.propositions.push({ ...p, projet: nom }));
    bilan.projets.push({ projet: nom, renforcees: renf, archivees: arch, resultat: resultats[i] || null });
  });
  return bilan;
}

/**
 * Choisit la source : démo si l'adresse contient ?demo=1 (ou si la page est le catalogue),
 * sinon le serveur réel ; si le serveur ne répond pas, on bascule en démo (badge affiché).
 */
export async function choisirSource({ forcerDemo = false } = {}) {
  const demande = forcerDemo || new URLSearchParams(location.search).get('demo') === '1';
  if (demande) return creerSourceDemo();
  const reelle = creerSourceReelle();
  try {
    await reelle.sphere();
    return reelle;
  } catch (e) {
    const demo = creerSourceDemo();
    demo.repli = 'Serveur indisponible : affichage de la démo (données fictives).';
    return demo;
  }
}

/**
 * Même routage par code que interface/conversation.py (pour lancer tout de suite la bonne
 * animation : vague de recherche ou simple balayage ; la réponse du serveur fait foi).
 */
export function routerReel(texte) {
  const brut = texte.trim();
  if (/^(?:ouvre|ouvrir|montre|affiche)(?:[- ]moi)? la note (.+?)\s*[?.!]*$/i.test(brut)) return 'ouvrir_note';
  const n = brut.toLowerCase().normalize('NFD').replace(/\p{M}/gu, '');
  if (/(simule|simuler)/.test(n) && /(nuit|reve|sommeil)/.test(n)) return 'nuit';
  const routes = [
    ['machine', /\b(machine|ordinateur|ordi|cpu|processeur|ram|memoire vive|disque|batterie|processus)\b/],
    ['meteo', /\b(meteo|pluie|pleuvoir|soleil|temps qu.il fait|temperature dehors)\b/],
    ['resume_nuit', /\b(nuit|dormi|sommeil|reveil)\b/],
    ['graphique', /\b(depenses?|budget|couts?|coute|facture|plafond)\b/],
    ['planification', /\b(planification|planning|planifier|agenda|taches?|demain|aujourd.hui|semaine|rendez.vous)\b/],
  ];
  for (const [nom, motif] of routes) if (motif.test(n)) return nom;
  return 'se_souvenir';
}
