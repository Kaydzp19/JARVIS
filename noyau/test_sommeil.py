"""
Tests de la marche 6 : sommeil (oubli + synthèse nocturne).
"""

from datetime import timedelta

from noyau import corps_calleux as cc
from noyau import projets, sommeil, synapses
from noyau.base_tests import JOUR_1, TestTemporaire


class TestSommeil(TestTemporaire):

    def setUp(self):
        super().setUp()
        projets.creer_projet("A", racine=self.racine)
        # Trois notes reliées en triangle, écrites (donc validées) par Kayd.
        self.a = cc.creer_note_humaine("A", "Clients", "Qui achète. Voir [[Prix]].",
                                       date=JOUR_1, racine=self.racine)
        self.b = cc.creer_note_humaine("A", "Prix", "Combien. Voir [[Offre]].",
                                       date=JOUR_1, racine=self.racine)
        self.c = cc.creer_note_humaine("A", "Offre", "Quoi. Voir [[Clients]].",
                                       date=JOUR_1, racine=self.racine)
        cc.modifier_note_humaine("A", self.a, "Qui achète. Voir [[Prix]] et [[Offre]].",
                                 date=JOUR_1, racine=self.racine)
        self.seule = cc.creer_note_humaine("A", "Divers", "Sans lien. Voir [[Clients]].",
                                           date=JOUR_1, racine=self.racine)

    def utiliser_pendant(self, jours):
        for i in range(jours):
            cc.activer("A", [self.a, self.b, self.c], date=JOUR_1 + timedelta(days=i),
                       racine=self.racine)

    def test_au_reveil_une_synthese_est_proposee_avec_sa_raison(self):
        self.utiliser_pendant(3)
        reveil = JOUR_1 + timedelta(days=3)
        bilan = sommeil.dormir(reveil, racine=self.racine)
        self.assertEqual(len(bilan["projets"]["A"]["syntheses_proposees"]), 1)
        p = cc.lister_propositions("A", "en attente", racine=self.racine)[0]
        self.assertEqual(p["type"], "synthese")
        self.assertEqual(set(p["liens"]), {"Clients", "Prix", "Offre"})
        self.assertNotIn("Divers", p["liens"])
        self.assertIn("très liées", p["raison"])
        journal = projets.lire_journal("A", racine=self.racine)
        self.assertTrue(any(l["acteur"] == "sommeil" and "1 synthèse" in l["raison"]
                            for l in journal))
        # Rien n'est écrit dans les notes avant la validation.
        self.assertEqual(len(projets.lister_notes("A", racine=self.racine)), 4)

    def test_pas_de_doublon_la_nuit_suivante(self):
        self.utiliser_pendant(3)
        sommeil.dormir(JOUR_1 + timedelta(days=3), racine=self.racine)
        bilan = sommeil.dormir(JOUR_1 + timedelta(days=4), racine=self.racine)
        self.assertEqual(bilan["projets"]["A"]["syntheses_proposees"], [])

    def test_sans_usage_pas_de_synthese_et_oubli_applique(self):
        bilan = sommeil.dormir(JOUR_1 + timedelta(days=3), racine=self.racine)
        self.assertEqual(bilan["projets"]["A"]["syntheses_proposees"], [])
        for s in synapses.lister_synapses("A", racine=self.racine):
            self.assertLess(s["poids"], 0.1)

    def test_la_synthese_validee_rejoint_le_cerveau(self):
        self.utiliser_pendant(3)
        sommeil.dormir(JOUR_1 + timedelta(days=3), racine=self.racine)
        pid = cc.lister_propositions("A", "en attente", racine=self.racine)[0]["id"]
        nid = cc.valider_proposition("A", pid, date=JOUR_1 + timedelta(days=3), racine=self.racine)
        cibles = {s["note_cible"] for s in synapses.lister_synapses("A", racine=self.racine)
                  if s["note_source"] == nid}
        self.assertEqual(cibles, {self.a, self.b, self.c})

    def test_fichier_launchd(self):
        texte = sommeil.plist_launchd("/Users/kayd/JARVIS", "/Users/kayd/.jarvis",
                                      python="/usr/bin/python3")
        self.assertIn("<string>/Users/kayd/JARVIS/jarvis.py</string>", texte)
        self.assertIn("<string>dormir</string>", texte)
        self.assertIn("<integer>3</integer>", texte)
