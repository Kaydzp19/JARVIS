/*
 * Démo en ligne de JARVIS : le « serveur » est remplacé par ce fichier.
 *
 * La page (copie de l'interface du vrai JARVIS) appelle /api/... comme d'habitude ;
 * ici, ces appels sont servis DANS LE NAVIGATEUR, à partir des fichiers data/*.json
 * (données fictives). Tout ce que tu fais (valider, refuser, simuler une nuit…) reste
 * en mémoire de la page : rien n'est enregistré, tout revient à zéro au rechargement.
 */
(function () {
  "use strict";
  var SIM = window.JarvisSimulation;
  var MASQUE = "(Contenu non publié dans la démo en ligne : seuls les titres et les liens le sont.)";
  var ETAT = { projets: [], donnees: {}, index: null, propres: {} };
  var fetchOrigine = window.fetch.bind(window);

  // ------------------------------------------------------------------ chargement
  var pret = fetchOrigine("data/projets.json").then(function (r) { return r.json(); }).then(function (index) {
    ETAT.index = index;
    return Promise.all(index.projets.map(function (p) {
      return fetchOrigine("data/" + p.fichier).then(function (r) { return r.json(); }).then(function (d) {
        ETAT.donnees[p.nom] = d; ETAT.projets.push(p.nom);
      });
    }));
  }).then(function () {
    ETAT.projets.sort();
  });
  window.JarvisDemo = { pret: pret, etat: ETAT };

  // ------------------------------------------------------------------ outils
  function maintenantIso() {
    var d = new Date(), z = function (n) { return String(n).padStart(2, "0"); };
    return d.getFullYear() + "-" + z(d.getMonth() + 1) + "-" + z(d.getDate()) + "T" + z(d.getHours()) + ":" + z(d.getMinutes()) + ":" + z(d.getSeconds());
  }
  function journal(d, evenement, raison, acteur) {
    var n = d.journal.reduce(function (m, l) { return Math.max(m, l.n); }, 0) + 1;
    d.journal.push({ n: n, date: maintenantIso(), acteur: acteur || "kayd (démo en ligne)", evenement: evenement, raison: raison || null });
  }
  function prochainId(liste) { return liste.reduce(function (m, x) { return Math.max(m, x.id); }, 0) + 1; }
  function aFaire(t) { return t.statut === "à faire" || t.statut === "pas fait"; }
  function titres(d) { var m = {}; d.notes.forEach(function (n) { m[n.titre] = n.id; }); return m; }
  function liensDuTexte(texte) {
    var r = [], re = /\[\[([^\[\]]+)\]\]/g, m;
    while ((m = re.exec(texte || ""))) { var t = m[1].trim(); if (t && r.indexOf(t) < 0) r.push(t); }
    return r;
  }
  function dateSynapses(d) {
    var actives = d.synapses.filter(function (s) { return !s.archivee; });
    if (!actives.length) return SIM.aujourdHui();
    return actives.map(function (s) { return s.jusqu_au; }).sort().pop();
  }
  function creerSynapse(d, a, b) {
    if (a === b || d.synapses.some(function (s) { return (s.a === a && s.b === b) || (s.a === b && s.b === a); })) return null;
    var s = { id: prochainId(d.synapses), a: a, b: b, poids: d.reglages.poids_initial, archivee: false,
              jusqu_au: dateSynapses(d), activations: 0, usages: [] };
    d.synapses.push(s); return s;
  }
  function contratSimple(d, t) {
    var note = d.notes.filter(function (n) { return n.id === t.note_id; })[0];
    return { projet: d.projet, tache_id: t.id, quoi: t.titre,
      pourquoi: note ? "Elle fait avancer « " + note.titre + " »." : "C'est la prochaine tâche du projet " + d.projet + ".",
      ou: note ? { note_id: note.id, titre: note.titre } : null,
      comment: [{ etape: "Préparer ce qu'il faut", duree_min: 10 }, { etape: "Faire : " + t.titre, duree_min: 25 },
                { etape: "Vérifier le résultat et le noter", duree_min: 5 }],
      duree_totale_min: 40, fin: ["Fait", "Pas fait"], apres: "Pause de 5 minutes, puis tâche suivante.", ia: "demo" };
  }
  function trierTaches(liste) {
    return liste.slice().sort(function (a, b) {
      var k = function (t) { return [t.statut === "à faire" ? 0 : 1, t.echeance || "9999-99-99", t.id]; };
      var x = k(a), y = k(b);
      for (var i = 0; i < 3; i++) { if (x[i] < y[i]) return -1; if (x[i] > y[i]) return 1; }
      return 0;
    });
  }

  // ------------------------------------------------------------------ les « routes » du serveur
  function etat(projet) {
    var projets = ETAT.projets.map(function (nom) {
      var d = ETAT.donnees[nom];
      return { nom: nom, sensible: d.sensible, demo: true, notes: d.notes.length,
               taches_a_faire: d.taches.filter(aFaire).length };
    });
    var d = ETAT.donnees[projet];
    var base = { projet: projet || null, mode_ia: "simule", projets: projets,
                 budget: { depense: 0, plafond: ETAT.index.budget.plafond }, modules: [] };
    if (!d) return Object.assign(base, { maintenant: null, taches: [], propositions: [], agents: [], journal: [], corps_calleux: [] });
    var journalDesc = d.journal.slice().sort(function (a, b) { return a.date < b.date ? 1 : a.date > b.date ? -1 : b.n - a.n; });
    var compte = {}, dernier = {};
    d.journal.forEach(function (l) {
      if (l.acteur.indexOf("agent:") === 0) { var nom = l.acteur.slice(6); compte[nom] = (compte[nom] || 0) + 1; dernier[nom] = l; }
    });
    var suivante = trierTaches(d.taches.filter(aFaire)).filter(function (t) { return t.contrat; })[0];
    return Object.assign(base, {
      maintenant: suivante ? suivante.contrat : null,
      taches: d.taches.map(function (t) { return { projet: projet, id: t.id, titre: t.titre, statut: t.statut, echeance: t.echeance, planifiee: !!t.contrat }; }),
      propositions: d.propositions.filter(function (p) { return p.statut === "en attente"; }).map(function (p) {
        return Object.assign({}, p, { projet: projet, contenu: MASQUE });
      }),
      agents: d.agents.map(function (a) {
        return Object.assign({}, a, { actions: compte[a.nom] || 0, etat: dernier[a.nom] ? "actif" : "en veille",
                                      dernier: dernier[a.nom] ? dernier[a.nom].evenement : null });
      }),
      journal: journalDesc.slice(0, 60).map(function (l) { return Object.assign({}, l, { projet: projet }); }),
      corps_calleux: journalDesc.filter(function (l) { return l.acteur === "claude (MCP)"; }).slice(0, 5)
    });
  }

  function cerveau(projet) {
    var d = ETAT.donnees[projet];
    if (!d) throw new Error("Projet inconnu : " + projet);
    var parTitre = titres(d), actives = d.synapses.filter(function (s) { return !s.archivee; });
    var passif = {
      neurones: d.notes.map(function (n) { return { id: "n" + n.id, titre: n.titre, validee: n.validee }; }),
      synapses: actives.map(function (s) { return { a: "n" + s.a, b: "n" + s.b, poids: Math.round(s.poids * 1000) / 1000 }; })
    };
    var actif = { neurones: [{ id: "o", titre: "orchestrateur", type: "orchestrateur" }], synapses: [] }, ponts = [];
    var agents = {};
    d.agents.forEach(function (a) {
      agents[a.nom] = a;
      actif.neurones.push({ id: "a:" + a.nom, titre: a.nom, type: "agent", voie: a.voie });
      actif.synapses.push({ a: "o", b: "a:" + a.nom, poids: 0.3 });
    });
    d.taches.filter(aFaire).forEach(function (t) {
      var id = "t" + t.id;
      actif.neurones.push({ id: id, titre: t.titre, type: "tache", statut: t.statut, planifiee: !!t.contrat });
      if (t.contrat && agents.planificateur) actif.synapses.push({ a: "a:planificateur", b: id, poids: 0.6 });
      if (t.note_id) ponts.push({ actif: id, passif: "n" + t.note_id });
    });
    var attente = d.propositions.filter(function (p) { return p.statut === "en attente"; });
    attente.forEach(function (p) {
      var id = "p" + p.id;
      actif.neurones.push({ id: id, titre: p.titre, type: "proposition", en_attente: true, proposition: p.id });
      var auteur = p.acteur.indexOf("agent:") === 0 ? p.acteur.slice(6) : null;
      if (auteur && agents[auteur]) actif.synapses.push({ a: "a:" + auteur, b: id, poids: 0.5 });
      if (p.verification && agents.verificateur) actif.synapses.push({ a: "a:verificateur", b: id, poids: 0.4 });
      var cibles = {};
      (p.liens || []).forEach(function (t) { if (parTitre[t]) cibles[parTitre[t]] = true; });
      if (p.note_cible) cibles[p.note_cible] = true;
      Object.keys(cibles).sort(function (a, b) { return a - b; }).forEach(function (nid) { ponts.push({ actif: id, passif: "n" + nid }); });
    });
    return { projet: projet, demo: true, sensible: d.sensible, passif: passif, actif: actif, ponts: ponts,
      compteurs: { passifs: passif.neurones.length, actifs: actif.neurones.length - 1, synapses: passif.synapses.length,
                   archivees: d.synapses.length - actives.length, en_attente: attente.length } };
  }

  function ideeDuJour(projet) {
    var d = ETAT.donnees[projet]; if (!d || !d.reves.length) return [];
    var derniere = d.reves.map(function (r) { return r.date; }).sort().pop();
    return d.reves.filter(function (r) { return r.date === derniere; });
  }

  function note(projet, id) {
    var d = ETAT.donnees[projet], n = d.notes.filter(function (x) { return x.id === id; })[0];
    if (!n) throw new Error("Note introuvable.");
    var parId = {}; d.notes.forEach(function (x) { parId[x.id] = x.titre; });
    var liens = [], retro = [];
    d.synapses.forEach(function (s) {
      if (s.a === id) liens.push({ titre: parId[s.b], id: s.b });
      if (s.b === id) retro.push({ titre: parId[s.a], id: s.a });
    });
    return { projet: projet, id: id, titre: n.titre, contenu: ETAT.propres[projet + ":" + id] || MASQUE,
             sensible: n.sensible, validee: n.validee, liens: liens, retroliens: retro };
  }

  function validerProposition(projet, id, action) {
    var d = ETAT.donnees[projet], p = d.propositions.filter(function (x) { return x.id === id; })[0];
    if (!p) throw new Error("Aucune proposition n°" + id + ".");
    if (p.statut !== "en attente") throw new Error("La proposition " + id + " est déjà « " + p.statut + " ».");
    if (action === "refuser") {
      p.statut = "refusée"; journal(d, "proposition " + id + " refusée", null); return { ok: true };
    }
    p.statut = "validée";
    var cree = null, parTitre = titres(d);
    if (p.type === "note" || p.type === "synthese") {
      cree = prochainId(d.notes);
      d.notes.push({ id: cree, titre: p.titre, validee: true, sensible: false });
      (p.liens || []).forEach(function (t) { if (parTitre[t]) creerSynapse(d, cree, parTitre[t]); });
      journal(d, "note créée : " + p.titre, "proposition " + id + " validée");
    } else if (p.type === "tache") {
      cree = prochainId(d.taches);
      var t = { id: cree, titre: p.titre, statut: "à faire", echeance: null,
                note_id: (p.liens && parTitre[p.liens[0]]) || null, contrat: null };
      t.contrat = contratSimple(d, t); d.taches.push(t);
      journal(d, "tâche créée : " + p.titre, "proposition " + id + " validée");
    } else if (p.type === "modification") {
      cree = p.note_cible;
      journal(d, "note modifiée : " + ((d.notes.filter(function (n) { return n.id === p.note_cible; })[0] || {}).titre || ""), "proposition " + id + " validée");
    }
    journal(d, "proposition " + id + " validée", null);
    return { ok: true, cree: cree };
  }

  function terminer(projet, id, fait) {
    var d = ETAT.donnees[projet], t = d.taches.filter(function (x) { return x.id === id; })[0];
    if (!t) throw new Error("Aucune tâche n°" + id + ".");
    t.statut = fait ? "fait" : "pas fait";
    journal(d, "tâche " + id + " : " + t.statut, null);
    journal(d, "notification (DEMO)", "Tâche " + id + " [" + projet + "] : " + (fait ? "FAIT" : "PAS FAIT") + ".", "module:notifications");
    return { ok: true, statut: t.statut };
  }

  function nuit(projet) {
    var d = ETAT.donnees[projet];
    var fin = SIM.prochaineNuit(d.synapses), bilan = SIM.appliquerNuits(d.synapses, fin, d.reglages);
    journal(d, "sommeil · tri (code)", "oubli appliqué : " + bilan.renforcees + " renforcement(s), " + bilan.archivees + " archivage(s)", "sommeil");
    journal(d, "nuit simulée en ligne", "nuit du " + fin);
    var lignes = bilan.evenements.length ? bilan.renforcees + " lien(s) renforcé(s) (+0,10), " + bilan.archivees + " archivé(s) sous 0,05"
                                         : "aucun usage cette nuit-là : chaque lien perd 2 %";
    return { nuit: fin, renforcees: bilan.renforcees, archivees: bilan.archivees, tri_propositions: [], syntheses_proposees: [],
             idees_revees: 0, reve: null, arret: null,
             message: "Nuit du " + fin.slice(8, 10) + "/" + fin.slice(5, 7) + " · tri : " + lignes
                      + ". En ligne, seules les synapses sont recalculées (l'analyse, le rêve et le réveil ont besoin du vrai JARVIS)." };
  }

  function decisionReve(projet, id, decision, raison) {
    var d = ETAT.donnees[projet], r = d.reves.filter(function (x) { return x.id === id; })[0];
    if (!r) throw new Error("Aucun rêve n°" + id + ".");
    r.statut = decision === "garder" ? "gardée" : "rejetée"; if (raison) r.raison = raison;
    journal(d, "rêve n°" + id + " " + r.statut + " : " + r.idee, raison || null);
    if (decision === "garder") {             // apprentissage : les notes sources se renforceront la nuit suivante
      var fin = SIM.prochaineNuit(d.synapses), veille = SIM.ajouterJours(fin, -1);
      for (var i = 0; i < r.sources.length; i++) for (var j = i + 1; j < r.sources.length; j++) {
        var s = creerSynapse(d, r.sources[i], r.sources[j]) ||
                d.synapses.filter(function (x) { return (x.a === r.sources[i] && x.b === r.sources[j]) || (x.a === r.sources[j] && x.b === r.sources[i]); })[0];
        if (s && s.usages.indexOf(veille) < 0) s.usages.push(veille);
      }
      journal(d, "apprentissage : rêve n°" + id + " gardé", "liens des notes sources renforcés la nuit suivante");
    }
    return { ok: true, statut: r.statut };
  }

  function enregistrerNote(projet, donnees) {
    var d = ETAT.donnees[projet], id = donnees.id;
    if (!id) {
      if (!String(donnees.titre || "").trim()) throw new Error("Donne un titre à la note.");
      id = prochainId(d.notes);
      d.notes.push({ id: id, titre: donnees.titre.trim(), validee: true, sensible: false });
      journal(d, "note créée : " + donnees.titre.trim(), "écrite par toi (démo en ligne, non enregistrée)");
    } else {
      journal(d, "note modifiée", "démo en ligne, non enregistrée");
    }
    ETAT.propres[projet + ":" + id] = donnees.contenu || "";
    var parTitre = titres(d);
    liensDuTexte(donnees.contenu).forEach(function (t) { if (parTitre[t]) creerSynapse(d, id, parTitre[t]); });
    return { ok: true, id: id };
  }

  // ------------------------------------------------------------------ fetch « intercepté »
  function reponse(statut, objet) {
    return new Response(JSON.stringify(objet), { status: statut, headers: { "Content-Type": "application/json" } });
  }
  function router(url, options) {
    var q = {}; url.searchParams.forEach(function (v, k) { q[k] = v; });
    var corps = options && options.body ? JSON.parse(options.body) : {};
    var methode = (options && options.method) || "GET", chemin = url.pathname.replace(/^.*\/api\//, "/api/");
    if (methode === "GET") {
      if (chemin === "/api/etat") return etat(q.projet);
      if (chemin === "/api/cerveau") return cerveau(q.projet);
      if (chemin === "/api/reve") return ideeDuJour(q.projet);
      if (chemin === "/api/journal") {
        var d = ETAT.donnees[q.projet], apres = Number(q.apres || 0);
        return d.journal.filter(function (l) { return l.n > apres; }).map(function (l) { return Object.assign({}, l, { projet: q.projet }); });
      }
      if (chemin === "/api/notes") return ETAT.donnees[q.projet].notes.map(function (n) { return { id: n.id, titre: n.titre, sensible: n.sensible }; });
      if (chemin === "/api/note") return note(q.projet, Number(q.id));
      if (chemin === "/api/ia") return { mode: "simule", budget: { depense: 0, plafond: 5, reste: 5 } };
    } else {
      if (chemin === "/api/proposition") return validerProposition(corps.projet, Number(corps.id), corps.action);
      if (chemin === "/api/tache") return terminer(corps.projet, Number(corps.id), !!corps.fait);
      if (chemin === "/api/nuit") return nuit(corps.projet);
      if (chemin === "/api/reve") return decisionReve(corps.projet, Number(corps.id), corps.decision, corps.raison);
      if (chemin === "/api/note") return enregistrerNote(corps.projet, corps);
      if (chemin === "/api/tour") {
        var dt = ETAT.donnees[ETAT.projets[0]];
        if (dt) journal(dt, "tour de l'orchestrateur", "démo en ligne : les agents ne tournent pas ici", "orchestrateur");
        return { actions: [], erreurs: [], appels_ia: 0 };
      }
    }
    throw new Error("Non disponible dans la démo en ligne.");
  }

  window.fetch = function (entree, options) {
    var url = new URL(typeof entree === "string" ? entree : entree.url, location.href);
    if (url.pathname.indexOf("/api/") < 0) return fetchOrigine(entree, options);
    return pret.then(function () {
      try { return reponse(200, router(url, options)); }
      catch (e) { return reponse(400, { erreur: e.message }); }
    });
  };
})();
