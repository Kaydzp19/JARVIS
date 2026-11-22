"""
Brique 6 : le sommeil s'articule avec les synapses et le corps calleux.
"""

from datetime import timedelta

from noyau import corps_calleux as cc
from noyau import projets, sommeil, synapses
from noyau.base_tests import JOUR_1, TestTemporaire
from noyau.client_mcp import ClientMCP


class TestArticulation(TestTemporaire):

    def setUp(self):
        super().setUp()
        projets.creer_projet("A", racine=self.racine)
        n = lambda t, x: cc.creer_note_humaine("A", t, x, date=JOUR_1, racine=self.racine)
        self.a = n("Clients", "Qui achète. Voir [[Prix]] et [[Offre]].")
        self.b = n("Prix", "Combien. Voir [[Offre]].")
        self.c = n("Offre", "Quoi. Voir [[Clients]].")

    def test_parcours_complet(self):
        from datetime import date
        aujourd_hui = date.today()  # le serveur MCP note l'usage à la vraie date du jour
        projets.creer_projet("J", racine=self.racine)
        n = lambda t, x: cc.creer_note_humaine("J", t, x, date=aujourd_hui, racine=self.racine)
        self.a = n("Clients", "Qui achète. Voir [[Prix]] et [[Offre]].")
        self.b = n("Prix", "Combien. Voir [[Offre]].")
        self.c = n("Offre", "Quoi. Voir [[Clients]].")
        # Le jour : Claude utilise les 3 notes ensemble, via le corps calleux (MCP).
        with ClientMCP(dossier=self.racine) as c:
            for _ in range(3):
                c.appeler("activer", projet="J", ids_notes=[self.a, self.b, self.c])
        s = synapses.synapse_entre("J", self.a, self.b, racine=self.racine)
        self.assertEqual(s["activations"], 3)  # chaque usage compte ; le gain, lui, est par nuit
        # La nuit : l'activation devient un renforcement, et une synthèse est proposée.
        avant = s["poids"]
        bilan = sommeil.dormir(aujourd_hui + timedelta(days=1), projet="J", racine=self.racine)
        apres = synapses.synapse_entre("J", self.a, self.b, racine=self.racine)["poids"]
        self.assertAlmostEqual(apres, 0.98 * avant + 0.10)
        self.assertGreaterEqual(bilan["projets"]["J"]["renforcees"], 3)

    def test_synthese_nocturne_validee_comme_les_autres(self):
        for i in range(3):
            cc.activer("A", [self.a, self.b, self.c], date=JOUR_1 + timedelta(days=i),
                       racine=self.racine)
        bilan = sommeil.dormir(JOUR_1 + timedelta(days=3), projet="A", racine=self.racine)
        pid = bilan["projets"]["A"]["syntheses_proposees"][0]
        p = cc.lire_proposition("A", pid, racine=self.racine)
        self.assertEqual((p["type"], p["statut"]), ("synthese", "en attente"))
        self.assertEqual(len(projets.lister_notes("A", racine=self.racine)), 3)
        nid = cc.valider_proposition("A", pid, racine=self.racine)
        self.assertEqual(len(projets.lister_notes("A", racine=self.racine)), 4)
        self.assertTrue(any(x["note_source"] == nid
                            for x in synapses.lister_synapses("A", racine=self.racine)))
        # La nuit suivante ne repropose pas la même synthèse.
        bilan = sommeil.dormir(JOUR_1 + timedelta(days=4), projet="A", racine=self.racine)
        self.assertEqual(bilan["projets"]["A"]["syntheses_proposees"], [])

    def test_nuit_simulee_enchaine_les_nuits(self):
        n1 = sommeil.nuit_simulee("A", racine=self.racine)
        n2 = sommeil.nuit_simulee("A", racine=self.racine)
        self.assertGreater(n2["nuit"], n1["nuit"])
        self.assertIsNone(n2["arret"])
        self.assertIn("idees_revees", n2)
