// Source de DÉMONSTRATION : fausses données, calculées dans le navigateur.
// Même format de réponses que le serveur réel (interface/conversation.py), pour que
// l'interface ne fasse aucune différence. Aucun texte de note : les notes fictives
// n'ont qu'un titre. Rien n'est enregistré.
// Logique pure (aucun accès au DOM) : testée dans Node.

import { valider, normaliser as normaliserEv } from './widgets/contrat.js';
import { empreinte, normaliser, rng } from './outils.js';
import * as PL from './planification.js';

export const PROJETS_DEMO = [
  { nom: 'Projet A', n: 96 }, { nom: 'Projet B', n: 72 }, { nom: 'Projet C', n: 52 },
];
const VOC = ['budget', 'routeur-ia', 'synapse', 'sommeil', 'garde-écriture', 'corps-calleux', 'journal',
  'dépôt-privé', 'étanchéité', 'secrets', 'serveur-mcp', 'recherche-fts5', 'oubli', 'renforcement',
  'tableau-de-bord', 'éditeur-notes', 'sphère-3d', 'voix', 'ollama', 'licence', 'open-source', 'sauvegarde',
  'tâches', 'propositions', 'réglages', 'poids', 'seuil-archivage', 'plafond-api', 'notes-sensibles',
  'démo', 'lisez-moi', 'idées', 'objectifs', 'décisions', 'contraintes', 'orchestrateur'];
export const ROUTEUR_SANS_IA = 'routeur : aucun appel IA';
const MOIS = ['janv.', 'févr.', 'mars', 'avr.', 'mai', 'juin', 'juil.', 'août', 'sept.', 'oct.', 'nov.', 'déc.'];

/** Le graphe de démo : 220 neurones (96, 72, 52) et environ 320 synapses, une région par projet. */
export function genererMemoire(graine = 23) {
  const r = rng(graine);
  let ident = 0;
  const projets = PROJETS_DEMO.map((p, pj) => {
    const neurones = [], pos = [];
    for (let i = 0; i < p.n; i++) {
      ident++;
      const t = VOC[(ident * 7 + pj * 3) % VOC.length] + (ident > VOC.length ? '-' + (Math.floor(ident / VOC.length) + 1) : '');
      neurones.push({ id: ident, titre: t, validee: r() > 0.08, sensible: false, liens: 0 });
      const a = r() * 6.2832, d = Math.sqrt(r());
      pos.push([d * Math.cos(a), d * Math.sin(a)]);
    }
    const synapses = [], vus = new Set();
    const ajouter = (i, j, w) => {
      const a = neurones[i].id, b = neurones[j].id, k = Math.min(a, b) + ':' + Math.max(a, b);
      if (i === j || vus.has(k)) return;
      vus.add(k);
      synapses.push({ a, b, poids: Math.round(w * 1000) / 1000 });
      neurones[i].liens++; neurones[j].liens++;
    };
    neurones.forEach((_, i) => {
      const proches = neurones.map((__, j) => [(pos[i][0] - pos[j][0]) ** 2 + (pos[i][1] - pos[j][1]) ** 2, j])
        .filter((x) => x[1] !== i).sort((x, y) => x[0] - y[0]).slice(0, r() < 0.1 ? 3 : 2);
      proches.forEach(([, j]) => {
        let w = 0.08 + 0.92 * Math.pow(r(), 1.6);
        if (r() < 0.07) w = 0.045 + r() * 0.011;          // presque oubliées
        ajouter(i, j, w);
      });
    });
    for (let q = 0; q < 8; q++) ajouter(Math.floor(r() * p.n), Math.floor(r() * p.n), 0.06 + r() * 0.2);
    neurones[Math.floor(p.n / 2)].sensible = pj === 1;
    return { nom: p.nom, sensible: pj === 1, demo: true, neurones, synapses, reves: [], propositions: [] };
  });
  return projets;
}

/** La même notation que noyau/corps_calleux.se_souvenir_trace (titres seulement en démo). */
export function tracer(projet, requete, limite = 6) {
  const notes = projet.neurones;
  const mots = normaliser(requete).split(/[^a-z0-9]+/).filter((m) => m.length >= 3);
  const h = empreinte(normaliser(requete));
  const pert = {}, force = {}, degre = {}, voisins = {};
  notes.forEach((n) => {
    const t = normaliser(n.titre);
    let s = mots.reduce((acc, m) => acc + (t.includes(m) ? 1 : 0), 0);
    // Sans texte, la démo ajoute une pertinence fictive mais stable pour cette question.
    s += ((empreinte(t) ^ h) % 97) / 97 * 0.6;
    pert[n.id] = s;
  });
  projet.synapses.forEach((s) => {
    (voisins[s.a] = voisins[s.a] || []).push([s.b, s.poids]);
    (voisins[s.b] = voisins[s.b] || []).push([s.a, s.poids]);
    [s.a, s.b].forEach((x) => { force[x] = (force[x] || 0) + s.poids; degre[x] = (degre[x] || 0) + 1; });
  });
  const max = (o) => Math.max(1e-9, ...Object.values(o), 0);
  const pmax = max(pert), fmax = max(force), dmax = max(degre);
  const base = {};
  notes.forEach((n) => {
    const fraicheur = 0.5 + 0.5 * ((empreinte(n.titre) % 10) / 10);
    const importance = 0.6 * (n.validee ? 1 : 0) + 0.4 * (degre[n.id] || 0) / dmax;
    base[n.id] = 0.55 * pert[n.id] / pmax + 0.25 * (force[n.id] || 0) / fmax + 0.1 * fraicheur + 0.1 * importance;
  });
  const ids = notes.map((n) => n.id);
  const graines = ids.slice().sort((a, b) => base[b] - base[a] || a - b).slice(0, 3);
  const propage = {};
  graines.forEach((g) => (voisins[g] || []).forEach(([v, w]) => { propage[v] = Math.max(propage[v] || 0, base[g] * w); }));
  const final = {};
  ids.forEach((i) => { final[i] = base[i] + 0.35 * (propage[i] || 0); });
  const retenues = ids.slice().sort((a, b) => final[b] - final[a] || a - b).slice(0, limite);
  // Dijkstra depuis les graines (coût d'une synapse = 1 / (0,12 + poids)).
  const dist = {}, avant = {}, fait = new Set();
  graines.forEach((g) => { dist[g] = 0; });
  for (;;) {
    let u = null, bd = Infinity;
    for (const i of ids) if (!fait.has(i) && (dist[i] ?? Infinity) < bd) { bd = dist[i]; u = i; }
    if (u == null) break;
    fait.add(u);
    (voisins[u] || []).forEach(([v, w]) => {
      const nd = bd + 1 / (0.12 + w);
      if (nd < (dist[v] ?? Infinity)) { dist[v] = nd; avant[v] = u; }
    });
  }
  const aretes = new Map(), inter = new Set();
  const poids = {};
  projet.synapses.forEach((s) => { const k = Math.min(s.a, s.b) + ':' + Math.max(s.a, s.b); poids[k] = Math.max(poids[k] || 0, s.poids); });
  retenues.forEach((i) => {
    let n = i, garde = 0;
    while (avant[n] != null && garde++ < 500) {
      const p = avant[n], a = Math.min(p, n), b = Math.max(p, n);
      aretes.set(a + ':' + b, { a, b, poids: poids[a + ':' + b] });
      if (!retenues.includes(p)) inter.add(p);
      n = p;
    }
  });
  const titres = Object.fromEntries(notes.map((n) => [n.id, n]));
  return {
    projet: projet.nom, requete, notees: notes.length, appel_ia: false, graines,
    retenues: retenues.map((i, r) => ({ id: i, titre: titres[i].titre, score: Math.round(final[i] * 1e4) / 1e4,
      pertinence: Math.round(pert[i] / pmax * 1e4) / 1e4, force: Math.round((force[i] || 0) * 1e3) / 1e3,
      sensible: !!titres[i].sensible, rang: r + 1 })),
    intermediaires: [...inter].sort((a, b) => a - b),
    synapses: [...aretes.values()].sort((x, y) => x.a - y.a || x.b - y.b),
  };
}

/** Routage de la démo par mots-clés (le vrai routeur est interface/conversation.py). */
export function router(texte) {
  const t = normaliser(texte);
  if (/sensible|prive|secret/.test(t)) return 'note_privee';
  if (/simule|simuler/.test(t) && /nuit|reve|sommeil/.test(t)) return 'nuit';
  if (/\bmac\b|machine|ordinateur|cpu|\bram\b|processeur|systeme|disque|batterie/.test(t)) return 'machine';
  if (/meteo|pluie|pleuvoir|temperature d/.test(t)) return 'meteo';
  if (/graphique|courbe|histogramme|depense|budget|cout/.test(t)) return 'graphique';
  if (/planification|planning|planifier|agenda|\btaches?\b|demain|aujourd.hui|semaine|rendez/.test(t)) return 'planification';
  if (/nuit|resume|bilan|sommeil/.test(t)) return 'resume_nuit';
  if (/carte|tableau|inconnu/.test(t)) return 'generique';
  return 'se_souvenir';
}

/** Choix du projet en démo : « projet A », « tous / mes projets », sinon le projet choisi. */
export function projetDemande(texte, choisi) {
  const t = normaliser(texte);
  const m = /projet\s*([abc])\b/.exec(t);
  if (m) return 'Projet ' + m[1].toUpperCase();
  if (/\b(projets|tous|toutes|avancement|ensemble)\b/.test(t)) return '*';
  return choisi;
}

export function creerSourceDemo(options = {}) {
  const r = rng(options.graine || 7);
  const projets = genererMemoire(options.graine || 23);
  const attente = [];          // propositions à valider (aucune au démarrage)
  const journal = [{ heure: options.heure || '08:00', projet: '—', acteur: 'jarvis', evenement: 'démarrage · mode démo, données fictives', prive: false }];
  let idAffichage = 0, idProposition = 0;
  const affichages = new Map();
  const sys = { cpu: 34, ram: 19.8, disque: 61, batterie: 87, hist: [] };
  for (let i = 0; i < 24; i++) sys.hist.push({ heure: '', cpu: 30 + 8 * Math.sin(i / 3) + r() * 6, ram: 62 });
  let derniereNuit = { renforcees: 14, archivees: 3, syntheses: 1, date: null };
  const aujourdHui = new Date();

  // ---- Planification (fausses tâches, en mémoire seulement) ----
  const deux = (n) => String(n).padStart(2, '0');
  const dateLocale = (d) => `${d.getFullYear()}-${deux(d.getMonth() + 1)}-${deux(d.getDate())}`;
  const auj = options.aujourdhui || dateLocale(aujourdHui);
  const taches = Object.fromEntries(projets.map((p) => [p.nom, []]));
  const titresNotes = Object.fromEntries(projets.map((p) => [p.nom, Object.fromEntries(p.neurones.map((n) => [n.id, n.titre]))]));
  let idTache = 0;
  const ajouterTache = (projet, champs) => {
    const notes = projets.find((p) => p.nom === projet).neurones;
    const t = PL.validerChamps(champs, { notes });
    idTache++;
    taches[projet].push({ id: idTache, statut: 'à faire', echeance: null, heure: null, rappel: null, note_id: null, ...t,
      ancre: t.recurrence !== 'aucune' ? t.echeance : null });
    return idTache;
  };
  [['Projet A', [['Revoir le budget', 0, '09:30', 45, 'haute', 'aucune', 0], ['Point d’équipe', 1, '10:00', 30, 'normale', 'hebdomadaire', 3],
    ['Écrire la synthèse', 2, '14:00', 90, 'normale', 'aucune', 5], ['Sport', 0, '18:30', 60, 'basse', 'jours_ouvres', null]]],
   ['Projet B', [['Préparer le rendez-vous', 1, '16:00', 60, 'haute', 'aucune', 7], ['Relire les idées', 3, '11:00', 30, 'normale', 'aucune', 9]]],
   ['Projet C', [['Tester la démo', 2, '09:00', 45, 'normale', 'aucune', 2], ['Rangement mensuel', 4, '17:00', 30, 'basse', 'mensuelle', null]]],
  ].forEach(([projet, liste]) => liste.forEach(([titre, j, heure, duree, priorite, recurrence, k]) => {
    const p = projets.find((x) => x.nom === projet);
    ajouterTache(projet, { titre, date: PL.plusJours(auj, j), heure, duree, priorite, recurrence, rappel: j === 0 ? 10 : null,
      note_id: k == null ? null : p.neurones[k].id });
  }));
  const trouverTache = (projet, id) => {
    const t = (taches[projet] || []).find((x) => x.id === Number(id));
    if (!t) throw new Error('Tâche introuvable.');
    return t;
  };
  function externes(debut, jours) {
    const modeles = [['Travail', 'Réunion d’équipe', '09:30', 60], ['Perso', 'Sport', '18:00', 60],
      ['Perso', 'Dentiste', '14:00', 45], ['Travail', 'Point client', '11:00', 30]];
    const ev = [];
    for (let i = 0; i < jours; i++) {
      const d = PL.plusJours(debut, i), js = (PL.versDate(d).getUTCDay() + 6) % 7;
      if (js > 4) continue;
      const [cal, titre, h, duree] = modeles[(PL.versDate(d).getTime() / 864e5 | 0) % modeles.length];
      const [hh, mm] = h.split(':').map(Number), fin = hh * 60 + mm + duree;
      ev.push({ calendrier: cal, titre, debut: `${d}T${h}`, fin: `${d}T${deux(Math.floor(fin / 60))}:${deux(fin % 60)}`, journee: false });
    }
    return { disponible: true, evenements: ev, source: 'démo', masque: false, modifiable: false };
  }
  function donneesPlanif(projet, debut = auj, vue = 'semaine') {
    let jours = 7;
    if (vue === 'semaine') debut = PL.lundi(debut);
    else if (vue === 'jour') jours = 1;
    const l = PL.lister(taches, projet, debut, jours, titresNotes);
    const p = projets.find((x) => x.nom === projet);
    return { projet, lecture_seule: projet === '*', vue, debut, jours, aujourd_hui: auj,
      projets: projets.map((x) => x.nom), taches: l.taches, sans_date: l.sans_date,
      notes: p ? p.neurones.map((n) => ({ id: n.id, titre: n.titre })) : [],
      externes: externes(debut, jours), priorites: PL.PRIORITES, recurrences: PL.RECURRENCES };
  }
  const evenementPlanif = (projet, debut, vue) => afficher({ scene: 'planification', titre: 'Planification', projet, fermeture: 0,
    donnees: donneesPlanif(projet, debut, vue),
    controles: { onglets: ['liste', 'jour', 'semaine'], filtres: projets.map((x) => x.nom).concat(['tous']) },
    actions: [{ id: 'precedent', libelle: '◀' }, { id: 'aujourdhui', libelle: 'Aujourd’hui' }, { id: 'suivant', libelle: '▶' }] });

  const note = (heure, projet, acteur, evenement, prive = false) => {
    journal.unshift({ heure, projet, acteur, evenement, prive });
    journal.length = Math.min(journal.length, 30);
  };
  const hm = () => { const d = new Date(); return String(d.getHours()).padStart(2, '0') + ':' + String(d.getMinutes()).padStart(2, '0'); };
  const trouver = (nom) => projets.find((p) => p.nom === nom);

  function machine() {
    sys.cpu = Math.max(12, Math.min(72, sys.cpu + (r() - 0.48) * 9));
    sys.ram = Math.max(17, Math.min(24, sys.ram + (r() - 0.5) * 0.5));
    sys.hist.push({ heure: hm(), cpu: Math.round(sys.cpu * 10) / 10, ram: Math.round(sys.ram / 32 * 1000) / 10 });
    sys.hist = sys.hist.slice(-24);
    const parts = [['ollama', 0.62], ['Claude', 0.14], ['Google Chrome', 0.11], ['python3', 0.06], ['WindowServer', 0.04]];
    return {
      cpu: Math.round(sys.cpu * 10) / 10,
      ram: { utilisee_go: Math.round(sys.ram * 10) / 10, totale_go: 32, pourcent: Math.round(sys.ram / 32 * 1000) / 10 },
      disque: { utilise_go: 628, total_go: 1000, pourcent: 62.8 },
      batterie: { pourcent: sys.batterie, en_charge: true },
      temperature: null, systeme: 'Darwin', heure: hm(),
      processus: parts.map(([nom, k]) => ({ nom, cpu: Math.round(k * sys.cpu * 10) / 10, ram: Math.round(k * 300) / 10 })),
      historique: sys.hist.slice(),
    };
  }

  function seriesDepenses(periode) {
    if (periode === '7 j' || periode === '30 j' || periode === '24 h') {
      const n = periode === '24 h' ? 1 : parseInt(periode, 10);
      return Array.from({ length: n }, (_, i) => {
        const d = new Date(aujourdHui); d.setDate(d.getDate() - (n - 1 - i));
        return { etiquette: String(d.getDate()).padStart(2, '0') + '/' + String(d.getMonth() + 1).padStart(2, '0'),
          valeur: Math.round(((empreinte('j' + i + n) % 30) / 100) * 100) / 100 };
      });
    }
    const n = periode === '12 mois' ? 12 : 6;
    return Array.from({ length: n }, (_, i) => {
      const d = new Date(aujourdHui.getFullYear(), aujourdHui.getMonth() - (n - 1 - i), 1);
      return { etiquette: MOIS[d.getMonth()], valeur: i === n - 1 ? 3.4 : Math.round((0.8 + (empreinte('m' + i) % 26) / 10 + i * 0.15) * 100) / 100 };
    });
  }
  const donneesDepenses = (periode = '6 mois') => ({ source: 'depenses_ia', type: 'barres', unite: '€', periode,
    serie: seriesDepenses(periode), plafond: 10, mois: 3.4, aujourd_hui: 0.12, session: 0 });

  function meteo() {
    const pts = [9, 9, 10, 11, 12, 12, 11, 10, 9, 8, 8, 7, 7, 7, 8, 9, 10, 11, 12, 12, 11, 10, 9, 9];
    const jours = ['lun', 'mar', 'mer', 'jeu', 'ven', 'sam', 'dim'];
    const codes = [3, 61, 61, 3, 0, 0, 3], hauts = [11, 9, 8, 10, 12, 13, 10];
    return { disponible: true, lieu: 'Paris', actuelle: { temperature: 9, code: 3 },
      heures: pts.map((v, i) => ({ heure: String((8 + i) % 24).padStart(2, '0') + ':00', temperature: v, pluie: i > 9 && i < 15 ? 70 : 10 })),
      jours: jours.map((j, i) => ({ date: j, code: codes[i], max: hauts[i], min: hauts[i] - 5 })) };
  }

  function nuitDonnees(nom) {
    return { projet: nom, date: derniereNuit.date || 'cette nuit', renforcees: derniereNuit.renforcees,
      archivees: derniereNuit.archivees, syntheses: derniereNuit.syntheses,
      idees_en_attente: attente.filter((p) => p.projet === nom).length,
      propositions_en_attente: attente.length, depense_mois: 3.4, plafond: 10 };
  }

  function afficher(ev) {
    const e = valider(ev);
    if (e.length) throw new Error('Affichage invalide : ' + e.join('; '));
    idAffichage++;
    const n = { ...normaliserEv(ev), id: idAffichage, version: 1 };
    affichages.set(n.id, n);
    return n;
  }

  const rep = (route, outil, reponse, affichage = null, recherche = null) =>
    ({ route, outil, routeur: ROUTEUR_SANS_IA, reponse, affichage, recherche, renforcement: null });

  return {
    mode: 'demo',
    peutSimulerNuit: true,
    async sphere() {
      const vues = projets.map((p) => ({ ...p, synapses: p.synapses.filter((x) => !x.archivee) }));
      return { projets: vues, demo: true, mode_ia: 'simule',
        compteurs: { neurones: vues.reduce((s, p) => s + p.neurones.length, 0),
          synapses: vues.reduce((s, p) => s + p.synapses.length, 0) } };
    },
    async demander(texte, choisi) {
      texte = (texte || '').trim();
      if (!texte) throw new Error('Message vide.');
      const route = router(texte), projet = projetDemande(texte, choisi);
      if (route === 'se_souvenir') {
        const cibles = projet === '*' ? projets : [trouver(projet) || projets[0]];
        const traces = cibles.map((p) => tracer({ ...p, synapses: p.synapses.filter((x) => !x.archivee) }, texte, projet === '*' ? 4 : 6));
        const ret = traces.flatMap((t) => t.retenues.map((x) => ({ ...x, projet: t.projet })));
        const nom = projet === '*' ? '*' : cibles[0].nom;
        const outil = `se_souvenir(projet="${nom}", requête="${texte.replace(/"/g, "'")}")`;
        const ev = afficher({ scene: 'notes_retenues', titre: 'Notes retenues', projet: nom,
          donnees: { requete: texte, notes: ret.map((x) => ({ id: x.id, titre: x.titre, projet: x.projet, score: x.score, rang: x.rang, sensible: x.sensible })) },
          controles: { tri: ['rang', 'score', 'titre'] },
          actions: nom === '*' ? [{ id: 'ouvrir_note', libelle: 'Ouvrir la note' }]
            : [{ id: 'ouvrir_note', libelle: 'Ouvrir la note' }, { id: 'creer_synthese', libelle: 'Proposer une synthèse', type: 'ecriture' }] });
        note(hm(), nom === '*' ? 'tous' : nom, 'se_souvenir', `${ret.length} notes retenues`);
        const titres = ret.slice(0, 3).map((x) => x.titre).join(', ');
        const reponse = nom === '*'
          ? `Vue transversale en lecture seule : j’ai parcouru les trois projets. Je retiens ${ret.length} notes, dont ${titres}. Aucun appel à l’IA n’a été nécessaire.`
          : `J’ai noté les ${traces[0].notees} neurones du ${nom}. Je retiens ${ret.length} notes, dont ${titres}. Aucun appel à l’IA n’a été nécessaire.`;
        return rep('se_souvenir', outil, reponse, ev, { projet: nom, traces });
      }
      if (route === 'nuit') return rep('nuit', 'sommeil.simuler()', '', null, null);
      if (route === 'planification') {
        const demain = /demain/.test(normaliser(texte)), jour = demain || /aujourd.hui/.test(normaliser(texte));
        const cible = projet === '*' ? '*' : (trouver(projet) ? projet : 'Projet A');
        const ev = evenementPlanif(cible, demain ? PL.plusJours(auj, 1) : auj, jour ? 'jour' : 'semaine');
        const n = ev.donnees.taches.filter((t) => t.statut !== 'fait').length;
        note(hm(), cible === '*' ? 'tous' : cible, 'affichage', 'planification');
        return rep('planification', `planification(projet="${cible}", vue="${ev.donnees.vue}", debut="${ev.donnees.debut}")`,
          `${n} tâche(s) à faire ${demain ? 'demain' : jour ? 'aujourd’hui' : 'cette semaine'}${cible === '*' ? ' dans tous tes projets (lecture seule)' : ` dans « ${cible} »`}. Les rendez-vous de l’agenda (démo) sont en violet.`, ev);
      }
      if (route === 'note_privee') {
        const b = trouver('Projet B'), privee = b.neurones.find((n) => n.sensible);
        const ev = afficher({ scene: 'note_privee', titre: 'Note sensible', projet: 'Projet B',
          donnees: { titre: privee.titre, id: privee.id, caracteres: 255 },
          actions: [{ id: 'ouvrir_note_locale', libelle: 'Ouvrir dans l’éditeur local' }] });
        note(hm(), 'Projet B', 'ouvrir_note', 'contenu privé, 255 caractères', true);
        return rep('ouvrir_note', `ouvrir_note(projet="Projet B", titre="${privee.titre}")`,
          'Cette note est marquée sensible : je ne l’affiche pas ici. Tu peux l’ouvrir toi-même dans l’éditeur local.', ev);
      }
      if (route === 'machine') {
        const ev = afficher({ scene: 'machine', titre: 'Machine', donnees: machine(), actions: [{ id: 'rafraichir', libelle: 'Actualiser' }] });
        note(hm(), '—', 'affichage', 'machine');
        return rep('machine', 'machine()', `Ton Mac est à ${String(ev.donnees.cpu).replace('.', ',')} % de CPU et ${String(ev.donnees.ram.utilisee_go).replace('.', ',')} Go de RAM sur 32. Ollama est le plus gourmand. La température du processeur reste indisponible sans droits administrateur.`, ev);
      }
      if (route === 'meteo') {
        const ev = afficher({ scene: 'meteo', titre: 'Météo', donnees: meteo(), actions: [{ id: 'rafraichir', libelle: 'Actualiser' }] });
        note(hm(), '—', 'affichage', 'météo');
        return rep('meteo', 'meteo()', 'À Paris : 9 °C, nuageux, de la pluie ce soir. Ce sont des données fictives de démonstration.', ev);
      }
      if (route === 'resume_nuit') {
        const nom = projet === '*' ? 'Projet A' : projet;
        const ev = afficher({ scene: 'resume_nuit', titre: 'Résumé de la nuit · ' + nom, projet: nom, donnees: nuitDonnees(nom) });
        note(hm(), nom, 'affichage', 'résumé de la nuit');
        return rep('resume_nuit', `resume_nuit(projet="${nom}")`, `Dernière nuit : ${derniereNuit.renforcees} synapses renforcées, ${derniereNuit.archivees} archivées, ${attente.length} idée(s) en attente de ta validation. Ce mois-ci, 3,40 € dépensés sur 10.`, ev);
      }
      if (route === 'graphique') {
        const ev = afficher({ scene: 'graphique', titre: 'Dépenses IA', donnees: donneesDepenses('6 mois'),
          controles: { periode: ['7 j', '30 j', '6 mois', '12 mois'] } });
        note(hm(), '—', 'affichage', 'graphique des dépenses');
        return rep('graphique', 'depenses_ia(periode="6 mois")', 'Voici tes dépenses IA sur six mois : ce mois-ci 3,40 € sur un plafond de 10 €. Données fictives de démonstration.', ev);
      }
      // Scène que l'interface ne connaît pas : widget générique.
      const ev = afficher({ scene: 'carte_projets', titre: 'Carte des projets', projet: '*',
        donnees: { lignes: projets.map((p) => ({ projet: p.nom, notes: p.neurones.length, synapses: p.synapses.length })) } });
      return rep('generique', 'affichage.creer(scene="carte_projets")', 'Je n’ai pas encore de vue dédiée à cette carte : je l’affiche sous forme de tableau.', ev);
    },
    async action(widget, action, params = {}) {
      const ev = affichages.get(Number(widget));
      if (!ev) throw new Error('Affichage inconnu.');
      const declaree = ev.actions.find((a) => a.id === action);
      if (!declaree && !['periode', 'onglet', 'filtre', 'tri', 'rafraichir'].includes(action)) throw new Error('Action non déclarée.');
      if (declaree && declaree.type === 'ecriture') {
        if (!ev.projet || ev.projet === '*') throw new Error('Action d’écriture hors projet : refusée.');
        idProposition++;
        const p = { projet: ev.projet, id: idProposition, titre: ('À valider : ' + declaree.libelle).slice(0, 80), type: 'tache',
          acteur: 'interface (widget)', raison: 'action d’écriture demandée depuis un hologramme', notes: [] };
        attente.push(p);
        note(hm(), ev.projet, 'garde_écriture', 'proposition à valider : ' + declaree.libelle);
        return { type: 'a_valider', proposition: p.id, projet: ev.projet };
      }
      let d = null;
      if (ev.scene === 'planification') {
        const vue = params.vue || ev.donnees.vue;
        let projet = params.projet || ev.donnees.projet;
        if (projet === 'tous') projet = '*';
        let debut = params.debut || ev.donnees.debut;
        const pas = vue === 'jour' ? 1 : 7;
        if (action === 'precedent') debut = PL.plusJours(debut, -pas);
        else if (action === 'suivant') debut = PL.plusJours(debut, pas);
        else if (action === 'aujourdhui') debut = auj;
        d = donneesPlanif(projet, debut, vue);
      }
      if (ev.scene === 'graphique') d = donneesDepenses(params.periode || ev.donnees.periode);
      else if (ev.scene === 'machine') d = machine();
      else if (ev.scene === 'meteo') d = meteo();
      note(hm(), ev.projet || '—', 'affichage.action', action);
      if (!d) return { type: 'inchange', affichage: ev };
      const maj = { ...ev, donnees: d, version: ev.version + 1 };
      affichages.set(maj.id, maj);
      return { type: 'mise_a_jour', affichage: maj };
    },
    async systeme() { return machine(); },
    /** ACTIONS HUMAINES sur les tâches (démo : en mémoire). */
    async taches(action, projet, { id, champs = {}, fait } = {}) {
      if (projet === '*' || !taches[projet]) throw new Error('La vue « tous les projets » est en lecture seule : choisis un projet.');
      const notes = trouver(projet).neurones;
      if (action === 'creer') {
        const nid = ajouterTache(projet, champs);
        note(hm(), projet, 'kayd', `tâche ${nid} créée : ${champs.titre}`);
        return { ok: true, id: nid };
      }
      const t = trouverTache(projet, id);
      if (action === 'modifier') {
        const c = PL.validerChamps(champs, { partiel: true, notes });
        Object.assign(t, c);
        if (t.recurrence !== 'aucune' && ('echeance' in c || 'recurrence' in c)) t.ancre = t.echeance;
        if (t.recurrence === 'aucune') t.ancre = null;
        note(hm(), projet, 'kayd', `tâche ${id} modifiée`);
        return { ok: true };
      }
      if (action === 'supprimer') {
        taches[projet].splice(taches[projet].indexOf(t), 1);
        note(hm(), projet, 'kayd', `tâche ${id} supprimée : ${t.titre}`);
        return { ok: true };
      }
      if (action === 'terminer') {
        const statut = fait ? 'fait' : 'pas fait';
        if (t.recurrence !== 'aucune' && t.echeance) {
          const avant = t.echeance;
          t.echeance = PL.prochaineDate(t.echeance, t.recurrence, t.ancre);
          note(hm(), projet, 'kayd', `tâche ${id} : ${statut} (occurrence du ${avant}), prochaine le ${t.echeance}`);
          return { ok: true, statut, prochaine: t.echeance };
        }
        t.statut = statut;
        note(hm(), projet, 'kayd', `tâche ${id} : ${statut}`);
        return { ok: true, statut, prochaine: null };
      }
      throw new Error('Action inconnue.');
    },
    async prochaines(nombre = 3) {
      const l = PL.lister(taches, '*', auj, 120, titresNotes).taches.filter((t) => t.statut !== 'fait');
      const vus = new Set(), r = [];
      for (const t of l) { const k = t.projet + t.id; if (vus.has(k)) continue; vus.add(k); r.push(t); if (r.length >= nombre) break; }
      return r;
    },
    async ouvrirPlanification(projet = '*', debut = auj, vue = 'semaine') { return evenementPlanif(projet, debut, vue); },
    async depenses() {
      return { session: 0, appels_session: 0, aujourd_hui: 0.12, mois: 3.4, plafond: 10, mode_ia: 'simule',
        serie: seriesDepenses('6 mois').map((x) => ({ mois: x.etiquette, montant: x.valeur })) };
    },
    async aValider() { return attente.map((p) => ({ ...p })); },
    async decider(projet, id, oui) {
      const i = attente.findIndex((p) => p.projet === projet && p.id === id);
      if (i < 0) throw new Error('Proposition introuvable.');
      const [p] = attente.splice(i, 1);
      note(hm(), projet, 'garde_écriture', (oui ? 'validée : ' : 'refusée : ') + p.titre);
      return { ok: true };
    },
    async journalDuJour() { return journal.map((l) => ({ ...l })); },
    async note(projet, id) {
      const p = trouver(projet), n = p && p.neurones.find((x) => x.id === id);
      if (!n) throw new Error('Note introuvable.');
      return { projet, id, titre: n.titre, contenu: '(Démo : les notes fictives n’ont pas de texte.)',
        sensible: n.sensible, demo: true, liens: [], retroliens: [] };
    },
    async enregistrerNote() { throw new Error('Démo : rien n’est enregistré.'); },
    /** Une nuit simulée sur les données de démo. Renvoie le bilan AVANT l'animation. */
    async simulerNuit() {
      const bilan = { projets: [], renforcees: [], archivees: [], propositions: [] };
      projets.forEach((p) => {
        // Même règle que noyau/synapses.py : poids = 0,98 × poids + 0,10 si la synapse a servi ;
        // archivage sous 0,05.
        const vivantes = p.synapses.filter((s) => !s.archivee);
        const renf = vivantes.filter(() => r() < 0.1);
        const arch = [];
        vivantes.forEach((s) => {
          const servie = renf.includes(s);
          s.poids = Math.min(1, Math.round((0.98 * s.poids + (servie ? 0.1 : 0)) * 1e6) / 1e6);
          if (servie) bilan.renforcees.push({ projet: p.nom, a: s.a, b: s.b });
          else if (s.poids < 0.05) { s.archivee = true; arch.push(s); bilan.archivees.push({ projet: p.nom, a: s.a, b: s.b }); }
        });
        let creee = null;
        if (!attente.some((x) => x.projet === p.nom)) {
          const ids = p.neurones.map((n) => n.id);
          const a = ids[Math.floor(r() * ids.length)];
          let b = ids[Math.floor(r() * ids.length)];
          if (b === a) b = ids[(ids.indexOf(a) + 7) % ids.length];
          idProposition++;
          const titres = Object.fromEntries(p.neurones.map((n) => [n.id, n.titre]));
          creee = { projet: p.nom, id: idProposition, type: 'synthese', acteur: 'sommeil (rêve)',
            titre: `Relier ${titres[a]} et ${titres[b]}`, raison: 'idée du rêve, 2 notes éloignées rapprochées', notes: [a, b] };
          attente.push(creee);
          bilan.propositions.push(creee);
        }
        bilan.projets.push({ projet: p.nom, renforcees: renf.length, archivees: arch.length, idee: creee ? creee.titre : null });
      });
      derniereNuit = { renforcees: bilan.renforcees.length, archivees: bilan.archivees.length,
        syntheses: bilan.propositions.length, date: 'cette nuit (simulée)' };
      note(hm(), 'tous', 'sommeil', `${bilan.renforcees.length} renforcées, ${bilan.archivees.length} archivées, ${bilan.propositions.length} idée(s)`);
      return bilan;
    },
  };
}
