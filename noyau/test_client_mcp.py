"""
Tests de la brique 2 (corps calleux) avec un VRAI client MCP qui lance le serveur
« python -m noyau.corps_calleux » dans un processus séparé, comme Claude Desktop.
"""

from noyau import corps_calleux as cc
from noyau import projets, synapses
from noyau.base_tests import JOUR_1, TestTemporaire
from noyau.client_mcp import ClientMCP, ErreurMCP


class TestClientMCP(TestTemporaire):

    def setUp(self):
        super().setUp()
        projets.creer_projet("Projet A", racine=self.racine)
        projets.creer_projet("Projet B", racine=self.racine)
        n = lambda p, t, x, **k: cc.creer_note_humaine(p, t, x, date=JOUR_1, racine=self.racine, **k)
        self.budget = n("Projet A", "Budget", "Le budget prévisionnel est de 300 euros.")
        self.plan = n("Projet A", "Plan", "Étapes du lancement. Voir [[Budget]].")
        n("Projet A", "Coffre", "Code secret 4242 du coffre.", sensible=True)
        n("Projet B", "Autre", "Une note du projet B sur le budget.")

    def journal(self, projet="Projet A"):
        return projets.lire_journal(projet, racine=self.racine)

    def test_session_complete_avec_les_4_messages(self):
        with ClientMCP(dossier=self.racine) as c:
            self.assertEqual(c.info["serverInfo"]["name"], "jarvis")
            self.assertEqual(c.outils(), ["se_souvenir", "proposer", "activer", "journal"])

            # 1. se_souvenir : lecture seule, FTS5 + poids des synapses
            avant = len(projets.lister_notes("Projet A", racine=self.racine))
            r = c.appeler("se_souvenir", projet="Projet A", requete="prévisionnel", limite=3)
            self.assertEqual(r[0]["titre"], "Budget")
            self.assertGreater(r[0]["pertinence"], 0)
            self.assertNotIn("Autre", [x["titre"] for x in r])          # étanchéité

            # 2. proposer : une proposition en attente, rien d'écrit
            p = c.appeler("proposer", projet="Projet A", type="note",
                          contenu="# Idée\nRelier le budget au plan.", liens=["Budget", "Plan"])
            self.assertEqual(p["statut"], "en attente")
            self.assertEqual(len(projets.lister_notes("Projet A", racine=self.racine)), avant)
            prop = cc.lire_proposition("Projet A", p["proposition"], racine=self.racine)
            self.assertEqual(prop["statut"], "en attente")
            self.assertEqual(prop["liens"], ["Budget", "Plan"])

            # 3. activer : renforce la synapse Plan → Budget (gain la nuit suivante)
            a = c.appeler("activer", projet="Projet A", ids_notes=[self.plan, self.budget])
            self.assertEqual(a["activees"], 1)
            s = synapses.synapse_entre("Projet A", self.plan, self.budget, racine=self.racine)
            self.assertEqual(s["activations"], 1)

            # 4. journal
            self.assertEqual(c.appeler("journal", projet="Projet A", evenement="test client",
                                       raison="depuis le client MCP"), {"ok": True})

        # Chaque appel est journalisé.
        evenements = [l["evenement"] for l in self.journal()]
        for outil in ("se_souvenir", "proposer", "activer"):
            self.assertIn(f"appel MCP : {outil}", evenements)
        self.assertIn("test client", evenements)
        self.assertTrue(all(l["acteur"] == "claude (MCP)" for l in self.journal()
                            if l["evenement"].startswith("appel MCP")))
        # Le projet B n'a rien reçu.
        self.assertFalse(any("MCP" in l["evenement"] for l in self.journal("Projet B")))

    def test_note_sensible_masquee(self):
        with ClientMCP(dossier=self.racine) as c:
            r = c.appeler("se_souvenir", projet="Projet A", requete="coffre")
        self.assertEqual(r[0]["titre"], "Coffre")
        self.assertNotIn("4242", r[0]["extrait"])

    def test_erreurs_propres(self):
        with ClientMCP(dossier=self.racine) as c:
            with self.assertRaises(ErreurMCP):
                c.appeler("se_souvenir", projet="Inconnu")
            with self.assertRaises(ErreurMCP):
                c.appeler("proposer", projet="Projet A", type="paiement", contenu="payer 100 €")
            with self.assertRaises(ErreurMCP):
                c.appeler("supprimer", projet="Projet A")       # outil qui n'existe pas
            self.assertEqual(c.demander("ping"), {})           # le serveur tient bon
        self.assertEqual(len(projets.lister_notes("Projet A", racine=self.racine)), 3)
