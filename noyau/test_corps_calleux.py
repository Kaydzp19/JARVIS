"""
Tests de la marche 3 : corps calleux (4 messages) et serveur MCP.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

from noyau import corps_calleux as cc
from noyau import projets, synapses
from noyau.base_tests import JOUR_1, TestTemporaire

RACINE_DEPOT = Path(__file__).resolve().parent.parent


class TestCorpsCalleux(TestTemporaire):

    def setUp(self):
        super().setUp()
        projets.creer_projet("A", racine=self.racine)
        projets.creer_projet("B", racine=self.racine)
        self.budget = cc.creer_note_humaine("A", "Budget", "Le budget du lancement est de 300.",
                                            date=JOUR_1, racine=self.racine)
        self.plan = cc.creer_note_humaine("A", "Plan", "Étapes du lancement. Voir [[Budget]].",
                                          date=JOUR_1, racine=self.racine)
        cc.creer_note_humaine("B", "Secret B", "Code d'accès du coffre.", date=JOUR_1,
                              racine=self.racine)

    # --- se_souvenir ---

    def test_se_souvenir_trouve_par_mot(self):
        r = cc.se_souvenir("A", "budget", racine=self.racine)
        self.assertEqual(r[0]["titre"], "Budget")
        self.assertIn("300", r[0]["extrait"])

    def test_se_souvenir_requete_vague_renvoie_les_notes_du_projet(self):
        r = cc.se_souvenir("A", "que sais-tu du projet A ?", racine=self.racine)
        self.assertEqual({n["titre"] for n in r}, {"Budget", "Plan"})

    def test_se_souvenir_est_etanche(self):
        r = cc.se_souvenir("A", "coffre", racine=self.racine)
        self.assertNotIn("Secret B", [n["titre"] for n in r])

    def test_se_souvenir_n_ecrit_rien(self):
        avant = len(projets.lire_journal("A", racine=self.racine))
        cc.se_souvenir("A", "budget", racine=self.racine)
        self.assertEqual(len(projets.lire_journal("A", racine=self.racine)), avant)

    def test_notes_sensibles_masquees(self):
        projets.creer_note("A", "Privé", "mot de passe banque", sensible=True, racine=self.racine)
        r = cc.se_souvenir("A", "banque", racine=self.racine, masquer_sensibles=True)
        self.assertEqual(r[0]["extrait"], cc.MASQUE_SENSIBLE)

    # --- proposer + garde d'écriture ---

    def test_proposer_n_ecrit_aucune_note(self):
        pid = cc.proposer("A", "note", "# Idée\nUne idée liée au [[Plan]].", liens=["Budget"],
                          date=JOUR_1, racine=self.racine)
        self.assertEqual(len(projets.lister_notes("A", racine=self.racine)), 2)
        p = cc.lire_proposition("A", pid, racine=self.racine)
        self.assertEqual(p["statut"], "en attente")
        self.assertEqual(p["titre"], "Idée")
        copie = projets.dossier_projet("A", self.racine) / "propositions" / f"{pid}.md"
        self.assertTrue(copie.exists())

    def test_valider_ecrit_la_note_validee_avec_synapses(self):
        pid = cc.proposer("A", "note", "# Idée\nVoir [[Plan]].", liens=["Budget"],
                          date=JOUR_1, racine=self.racine)
        nid = cc.valider_proposition("A", pid, date=JOUR_1, racine=self.racine)
        self.assertTrue(synapses.note_validee("A", nid, racine=self.racine))
        cibles = {s["note_cible"] for s in synapses.lister_synapses("A", racine=self.racine)
                  if s["note_source"] == nid}
        self.assertEqual(cibles, {self.plan, self.budget})
        self.assertEqual(cc.lire_proposition("A", pid, racine=self.racine)["statut"], "écrite")
        with self.assertRaises(ValueError):
            cc.valider_proposition("A", pid, racine=self.racine)

    def test_refuser_n_ecrit_rien(self):
        pid = cc.proposer("A", "tache", "Appeler le fournisseur", racine=self.racine)
        cc.refuser_proposition("A", pid, racine=self.racine)
        self.assertEqual(projets.lister_taches("A", racine=self.racine), [])
        self.assertEqual(cc.lire_proposition("A", pid, racine=self.racine)["statut"], "refusée")

    def test_types_dangereux_refuses(self):
        for t in ("publication", "paiement", "suppression"):
            with self.assertRaises(ValueError):
                cc.proposer("A", t, "x", racine=self.racine)

    # --- activer + journal ---

    def test_activer_renforce_la_nuit_suivante(self):
        avant = synapses.synapse_entre("A", self.plan, self.budget, racine=self.racine)["poids"]
        bilan = cc.activer("A", [self.plan, self.budget], date=JOUR_1, racine=self.racine)
        self.assertEqual(bilan["activees"], 1)
        from datetime import timedelta
        synapses.appliquer_oubli("A", JOUR_1 + timedelta(days=1), racine=self.racine)
        apres = synapses.synapse_entre("A", self.plan, self.budget, racine=self.racine)["poids"]
        self.assertGreater(apres, avant)

    def test_journal_ajoute_une_ligne(self):
        cc.journal("A", "essai", "pour voir", racine=self.racine, acteur="test")
        derniere = projets.lire_journal("A", racine=self.racine)[-1]
        self.assertEqual((derniere["evenement"], derniere["raison"], derniere["acteur"]),
                         ("essai", "pour voir", "test"))


class TestServeurMCP(TestTemporaire):
    """Lance le vrai serveur dans un processus séparé, comme Claude Desktop."""

    def dialoguer(self, messages):
        env = dict(os.environ)
        entree = "\n".join(json.dumps(m) for m in messages) + "\n"
        sortie = subprocess.run([sys.executable, str(RACINE_DEPOT / "jarvis.py"), "mcp"],
                                input=entree, capture_output=True, text=True, env=env,
                                timeout=30, cwd=str(self.racine))
        self.assertEqual(sortie.returncode, 0, sortie.stderr)
        return [json.loads(l) for l in sortie.stdout.splitlines() if l.strip()]

    def test_dialogue_complet(self):
        projets.creer_projet("A", racine=self.racine)
        cc.creer_note_humaine("A", "Objectif", "Lancer la première version en mars.",
                              date=JOUR_1, racine=self.racine)
        reponses = self.dialoguer([
            {"jsonrpc": "2.0", "id": 1, "method": "initialize",
             "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                        "clientInfo": {"name": "test", "version": "1"}}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
             "params": {"name": "se_souvenir",
                        "arguments": {"projet": "A", "requete": "que sais-tu du projet A ?"}}},
            {"jsonrpc": "2.0", "id": 4, "method": "tools/call",
             "params": {"name": "se_souvenir", "arguments": {"projet": "Inconnu"}}},
        ])
        self.assertEqual(len(reponses), 4)  # la notification n'a pas de réponse
        self.assertEqual(reponses[0]["result"]["serverInfo"]["name"], "jarvis")
        noms = [o["name"] for o in reponses[1]["result"]["tools"]]
        self.assertEqual(noms, ["se_souvenir", "proposer", "activer", "journal"])
        texte = reponses[2]["result"]["content"][0]["text"]
        self.assertIn("Objectif", texte)
        self.assertIn("mars", texte)
        self.assertTrue(reponses[3]["result"]["isError"])
        # Chaque appel est journalisé.
        journal = projets.lire_journal("A", racine=self.racine)
        self.assertTrue(any("appel MCP : se_souvenir" in l["evenement"] for l in journal))
