// Point d'entrée de l'interface « sphère » : relie la source de données, la sphère,
// la conversation, le tableau de bord, l'éditeur et les hologrammes.
// L'interface ne décide rien : elle envoie la question, montre la trace et affiche
// ce que JARVIS a écrit (événements d'affichage). Les décisions restent à Kayd.

import { $, el, heureMinute } from './outils.js';
import { choisirSource, routerReel } from './donnees.js';
import { projetDemande, router as routerDemo } from './donnees_demo.js';
import { creerSphere } from './sphere.js';
import { creerConversation } from './conversation.js';
import { creerTableau } from './tableau.js';
import { creerEditeur } from './editeur.js';
import { creerHologrammes } from './widgets/hologramme.js';

const SUGGESTIONS_DEMO = ['Que sais-tu du projet A ?', 'Où en sont mes projets ?', 'État de mon Mac', 'Météo à Paris',
  'Résumé de la nuit', 'Graphique de mes dépenses', 'Simule une nuit', 'Ouvre ma note sensible'];
const SUGGESTIONS_REELLES = ['Que sais-tu de ce projet ?', 'Où en sont mes projets ?', 'État de ma machine', 'Météo',
  'Résumé de la nuit', 'Graphique de mes dépenses'];
const pause = (ms) => new Promise((r) => setTimeout(r, ms));

function horloge() {
  const d = new Date();
  $('horloge').textContent = d.toLocaleDateString('fr-FR', { weekday: 'short', day: 'numeric', month: 'short' }).replace('.', '') + ' · ' + heureMinute(d);
}

function onde(etatVoix) {
  const svg = $('onde'), barres = [];
  for (let i = 0; i < 34; i++) {
    const r = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
    r.setAttribute('x', i * 6); r.setAttribute('width', 3); r.setAttribute('rx', 1.5); r.setAttribute('y', 8); r.setAttribute('height', 2);
    svg.appendChild(r); barres.push(r);
  }
  (function tic(t) {
    barres.forEach((r, i) => {
      const h = etatVoix.parle ? 3 + 13 * Math.abs(Math.sin(t / 130 + i * 0.7) * Math.sin(t / 310 + i * 0.31)) : 2;
      r.setAttribute('height', h); r.setAttribute('y', 9 - h / 2);
    });
    requestAnimationFrame(tic);
  })(0);
}

/** Sans WebGL : message clair et liste des notes (titres seulement). */
function sansWebGL(donnees) {
  const b = $('sansgl');
  b.hidden = false;
  b.appendChild(el('h3', '', 'WebGL n’est pas disponible dans ce navigateur : la sphère 3D ne peut pas s’afficher.'));
  b.appendChild(el('p', '', 'Utilise un Chrome ou un Safari récent. En attendant, voici tes notes (titres seulement) :'));
  donnees.projets.forEach((p) => {
    b.appendChild(el('h4', '', `${p.nom} · ${p.neurones.length} notes`));
    const u = el('ul');
    p.neurones.slice(0, 200).forEach((n) => u.appendChild(el('li', '', n.titre + (n.sensible ? ' (sensible)' : ''))));
    b.appendChild(u);
  });
  $('legende').hidden = true;
}

async function demarrer() {
  const page = document.body.dataset.page || 'interface';
  // data-mode="demo-en-ligne" : site statique (Vercel), sans serveur : démo dans le navigateur.
  const enLigne = document.body.dataset.mode === 'demo-en-ligne';
  const source = await choisirSource({ forcerDemo: page === 'catalogue' || enLigne });
  if (enLigne) source.repli = 'Démo en ligne : données fictives, calculées dans ton navigateur. Rien n’est enregistré. '
    + 'Pose une question, ou essaie « Simule une nuit ».';
  let donnees = await source.sphere();
  const demo = source.mode === 'demo' || !!donnees.demo;
  $('badge-demo').hidden = !demo;
  if (source.repli && !enLigne) $('lien-cockpit').hidden = true;
  if (source.mode === 'reel') source.peutSimulerNuit = donnees.projets.some((p) => p.demo);
  horloge(); setInterval(horloge, 20000);

  const etatVoix = { parle: false };
  onde(etatVoix);
  const annoncer = (t) => { $('annonce').textContent = t; };
  const compteur = (c) => { $('compteur').textContent = `${c.neurones} neurones · ${c.synapses} synapses · ${c.archivees} archivées`; };

  const sphere = creerSphere($('scene'), { auChangement: compteur, annoncer });
  if (sphere) {
    sphere.S.ecrirePhase = (t) => { $('phase').textContent = t; };
    sphere.charger(donnees);
  } else sansWebGL(donnees);
  if (!donnees.projets.length) {
    $('vide').hidden = false;
    $('vide').innerHTML = 'Aucun projet pour l’instant.<br>Crée les projets de démonstration avec <code>python3 jarvis.py demo</code>, '
      + 'ou ouvre la démo fictive : <a href="?demo=1" style="color:#4CC9FF">?demo=1</a>.';
  }
  const voix = {
    parler(n) { etatVoix.parle = n > 0; if (sphere) sphere.parler(n); },
    ecouter(o) { if (sphere) sphere.ecouter(o); },
  };

  // Choix du projet interrogé (un projet à la fois ; « tous » = lecture seule).
  const choix = $('projet');
  donnees.projets.forEach((p) => { const o = el('option', '', p.nom + (p.sensible ? ' (sensible)' : '')); o.value = p.nom; choix.appendChild(o); });
  const tous = el('option', '', 'Tous les projets · lecture seule'); tous.value = '*'; choix.appendChild(tous);

  let conv, holo = null, editeur;
  const message = (t) => conv && conv.dire(t);

  async function synchroniserAlertes() {
    const liste = await tableau.aValider();
    if (!sphere) return;
    let props = liste;
    if (source.mode === 'reel') {
      try {
        const d = await source.sphere();
        const notes = new Map();
        d.projets.forEach((p) => p.propositions.forEach((x) => notes.set(p.nom + ':' + x.id, x.notes)));
        props = liste.map((x) => ({ ...x, notes: notes.get(x.projet + ':' + x.id) || [] }));
      } catch (e) { /* on garde la liste sans notes */ }
    }
    sphere.synchroniserAlertes(props);
  }
  const tableau = creerTableau({
    source,
    async surDecision(p, oui) {
      try {
        await source.decider(p.projet, p.id, oui);
        conv.outil(`garde_écriture · ${oui ? 'validée' : 'refusée'} : ${p.titre}`, 'décision de Kayd, journalisée');
      } catch (e) { conv.outil('garde_écriture · erreur', e.message); }
      await synchroniserAlertes();
      tableau.journal();
    },
  });

  editeur = creerEditeur({ source, surMessage: message });

  if (sphere) {
    holo = creerHologrammes({
      sphere, centre: $('centre'), annoncer, vivant: () => tableau.machine,
      async surAction(ev, action, params) {
        try {
          const r = await source.action(ev.id, action, params);
          if (r.type === 'mise_a_jour') holo.appliquer(r.affichage);
          else if (r.type === 'a_valider') {
            conv.outil(`affichage.action(widget=${ev.id}, action="${action}")`, 'écriture : rien n’est exécuté, proposition à valider créée');
            await synchroniserAlertes();
          }
          tableau.journal();
        } catch (e) { conv.outil(`affichage.action(widget=${ev.id}, action="${action}")`, { texte: 'refusée : ' + e.message, prive: true }); }
      },
      surNote(n) { sphere.allumer(n.projet, n.id); },
      surOuvrirNote(n) {
        if (n.sensible) { conv.outil('ouvrir_note · refusé', { texte: 'note sensible : elle reste fermée ici', prive: true }); return; }
        editeur.ouvrir(n.projet, n.id, { depuisWidget: true });
      },
    });
  }

  function afficher(ev) {
    if (!ev) return;
    if (!holo) { conv.outil(`affichage.creer(scene="${ev.scene}")`, 'hologramme non affichable sans WebGL'); return; }
    const r = holo.appliquer(ev);
    if (r.geste === 'refuser') conv.outil(`affichage refusé (scène « ${ev.scene} »)`, { texte: r.erreurs.join(' ; '), prive: true });
    return r;
  }

  async function demander(texte) {
    if (conv.occupe) return;
    conv.verrouiller(true);
    conv.ajouter('u', 'TOI', texte);
    conv.etat('ANALYSE');
    if (holo) holo.fermer();
    const projet = (() => {
      const p = projetDemande(texte, choix.value);
      return p === '*' || donnees.projets.some((x) => x.nom === p) ? p : choix.value;
    })();
    const route = source.mode === 'demo' ? routerDemo(texte) : routerReel(texte);
    try {
      if (route === 'nuit') {
        if (!source.peutSimulerNuit || !sphere) { await conv.dire('La nuit simulée est réservée aux projets de démonstration. Les vraies nuits passent par « python3 jarvis.py dormir ».'); return; }
        conv.outil('sommeil.simuler()', 'quatre phases accélérées · rien n’est écrit sans validation');
        const projetsDemo = donnees.projets.filter((p) => p.demo).map((p) => p.nom);
        const bilan = await source.simulerNuit(projetsDemo);
        const info = await sphere.nuit(bilan);
        await synchroniserAlertes();
        tableau.journal(); tableau.depenses();
        await conv.dire(`Nuit simulée : ${info.renforcees} synapses renforcées, ${info.archivees} archivées, ${info.idees} idée${info.idees > 1 ? 's' : ''} en attente de ta validation.`);
        return;
      }
      if (route === 'se_souvenir' && sphere) {
        const poignee = sphere.rechercher(projet);
        const reponse = await source.demander(texte, projet);
        if (!reponse.recherche) { poignee && poignee.annuler(); }
        const ligne = conv.outil(reponse.outil || '—', reponse.routeur + (reponse.recherche ? ' · notation par code' : ''));
        if (reponse.recherche && poignee) {
          poignee.fournir(reponse.recherche.traces);
          const sel = await poignee.reponse;
          if (sel) ligne.completer(`${sel.notees} neurones notés · ${sel.retenues.length} notes retenues · ${sel.liens} liens utilisés`);
        }
        afficher(reponse.affichage);
        await conv.dire(reponse.reponse);
        tableau.journal();
        return;
      }
      // Hologramme qui n'est pas une recherche : la même vague, seule (3 s), le précède.
      const [reponse] = await Promise.all([source.demander(texte, projet), sphere ? sphere.balayer() : pause(600)]);
      conv.outil(reponse.outil || '—', reponse.routeur);
      afficher(reponse.affichage);
      if (reponse.ouvrir_note) editeur.ouvrir(reponse.ouvrir_note.projet, reponse.ouvrir_note.id);
      await conv.dire(reponse.reponse || '…');
      tableau.journal();
    } catch (e) {
      await conv.dire(`Je n’ai pas pu répondre : ${e.message}`);
    } finally {
      conv.verrouiller(false);
    }
  }

  conv = creerConversation({ sphere: voix, surQuestion: demander });
  conv.proposer(source.mode === 'demo' ? SUGGESTIONS_DEMO
    : SUGGESTIONS_REELLES.concat(source.peutSimulerNuit ? ['Simule une nuit'] : []));
  const nb = donnees.projets.length;
  conv.ajouter('j', 'JARVIS', source.repli ? source.repli
    : nb ? `Bonjour Kayd. ${nb} projet${nb > 1 ? 's' : ''} en mémoire. Touche un neurone, ou pose une question. Quand tu as besoin d’un visuel, je crée un hologramme, puis il disparaît.`
      : 'Bonjour Kayd. Aucun projet pour l’instant.');
  tableau.demarrer();
  synchroniserAlertes();

  if (page === 'catalogue') installerCatalogue({ demander, holo, conv });
  window.__JARVIS = { pret: true, source, sphere, holo, demander, mode: source.mode,
    get occupe() { return conv.occupe; } };
}

/** Page catalogue : chaque scène avec de fausses données, et les cas limites. */
function installerCatalogue({ demander, holo }) {
  const liste = $('catalogue-liste'), sortie = $('catalogue-sortie');
  const cas = [
    ['Notes retenues', 'vague complète en 4 temps, projet A', () => demander('Que sais-tu du projet A ?')],
    ['Tous les projets', 'lecture seule, 4 notes par projet', () => demander('Où en sont mes projets ?')],
    ['Graphique 3D', 'dépenses IA sur 6 mois, plafond 10 €, période modifiable', () => demander('Graphique de mes dépenses')],
    ['Machine', 'jauges, processus, courbe 2 min, puce 3D', () => demander('État de mon Mac')],
    ['Météo', 'soleil et nuage 3D, 24 h, 7 jours', () => demander('Météo à Paris')],
    ['Résumé de la nuit', 'barres 3D : renforcées, archivées, en attente, dépense', () => demander('Résumé de la nuit')],
    ['Note sensible refusée', 'cadenas 3D, contenu privé', () => demander('Ouvre ma note sensible')],
    ['Scène inconnue', 'repli : widget générique (tableau)', () => demander('Montre la carte des projets')],
    ['Événement invalide', 'refusé par le schéma (texte de note)', () => {
      const r = holo && holo.appliquer({ scene: 'notes_retenues', titre: 'Essai', donnees: { notes: [{ titre: 'x', contenu: 'secret' }] } });
      sortie.textContent = r ? `Refusé : ${r.erreurs.join(' ; ')}` : 'WebGL absent.';
    }],
    ['Nuit simulée', 'tri, analyse, rêve, réveil (proposition jaune)', () => demander('Simule une nuit')],
  ];
  cas.forEach(([titre, detail, faire]) => {
    const b = el('button'); b.type = 'button';
    b.appendChild(document.createTextNode(titre)); b.appendChild(el('small', '', detail));
    b.addEventListener('click', faire);
    liste.appendChild(b);
  });
}

demarrer().catch((e) => {
  const v = $('vide');
  v.hidden = false;
  v.textContent = 'Démarrage impossible : ' + e.message;
  console.warn(e);
});
