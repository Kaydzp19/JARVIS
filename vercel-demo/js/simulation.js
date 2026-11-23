/*
 * Simulation des synapses de JARVIS, en JavaScript (démo en ligne).
 * Copie fidèle de noyau/synapses.py : appliquer_oubli et prochaine_nuit.
 * Une nuit : poids = (1 - oubli) × poids + apprentissage × (1 si les deux notes
 * ont servi ensemble ce jour-là, sinon 0), plafonné à 1 ; sous le seuil, archivage.
 * Marche dans le navigateur (window.JarvisSimulation) et dans Node (tests).
 */
(function (racine) {
  "use strict";

  function ajouterJours(iso, n) {
    var p = String(iso).slice(0, 10).split("-").map(Number);
    var d = new Date(Date.UTC(p[0], p[1] - 1, p[2] + n));
    return d.toISOString().slice(0, 10);
  }

  function aujourdHui() {
    var d = new Date();
    return new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate())).toISOString().slice(0, 10);
  }

  /* La nuit qui suit la dernière nuit déjà calculée (synapses actives). */
  function prochaineNuit(synapses) {
    var dates = synapses.filter(function (s) { return !s.archivee; }).map(function (s) { return s.jusqu_au; });
    var max = dates.length ? dates.sort()[dates.length - 1] : aujourdHui();
    return ajouterJours(max, 1);
  }

  /* Calcule toutes les nuits jusqu'à « fin » (texte AAAA-MM-JJ). Modifie les synapses. */
  function appliquerNuits(synapses, fin, reglages) {
    var r = reglages, bilan = { renforcees: 0, archivees: 0, evenements: [] };
    synapses.forEach(function (s) {
      if (s.archivee) return;
      var jour = String(s.jusqu_au).slice(0, 10);
      if (jour >= fin) return;
      var usages = {};
      (s.usages || []).forEach(function (u) { usages[String(u).slice(0, 10)] = true; });
      var poids = s.poids, archivee = false;
      while (jour < fin) {
        var servi = usages[jour] ? 1 : 0, ancien = poids;
        poids = (1 - r.oubli) * poids + r.apprentissage * servi;
        poids = Math.max(0.0, Math.min(r.plafond, poids));
        jour = ajouterJours(jour, 1);
        if (servi) {
          bilan.renforcees += 1;
          bilan.evenements.push({ type: "renforcee", synapse: s.id, jour: jour, avant: ancien, apres: poids });
        }
        if (poids < r.seuil_archivage) {
          archivee = true; bilan.archivees += 1;
          bilan.evenements.push({ type: "archivee", synapse: s.id, jour: jour, apres: poids });
          break;
        }
      }
      s.poids = poids; s.archivee = archivee; s.jusqu_au = jour;
    });
    return bilan;
  }

  var api = { ajouterJours: ajouterJours, aujourdHui: aujourdHui, prochaineNuit: prochaineNuit,
              appliquerNuits: appliquerNuits };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else racine.JarvisSimulation = api;
})(typeof window !== "undefined" ? window : this);
