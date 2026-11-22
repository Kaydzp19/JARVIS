"""
Tests de la marche 6, partie 3 : phase d'analyse (résumé du projet, limite de jetons).
"""

import json

from noyau import corps_calleux as cc
from noyau import projets, sommeil
from noyau.base_tests import JOUR_1, TestTemporaire
from noyau.test_sommeil_tri import Espion


class TestAnalyse(TestTemporaire):

    def setUp(self):
        super().setUp()
        projets.creer_projet("A", racine=self.racine)
        self.espion = Espion()
        cc.creer_note_humaine("A", "Plan", "Les étapes du lancement. Voir [[Budget]].",
                              date=JOUR_1, racine=self.racine)
        cc.creer_note_humaine("A", "Budget", "Trois cents euros pour commencer.",
                              date=JOUR_1, racine=self.racine)
        cc.creer_note_humaine("A", "Privé", "Mon code secret 9876.", sensible=True,
                              date=JOUR_1, racine=self.racine)
        projets.creer_tache("A", "Écrire le plan", racine=self.racine)

    def dormir(self):
        return sommeil.dormir(JOUR_1, projet="A", racine=self.racine,
                              fournisseurs={"demo": self.espion})

    def demandes(self, tache):
        return [json.loads(t) for nom, t, _ in self.espion.recus if nom == tache]

    def test_resume_du_projet_enregistre(self):
        bilan = self.dormir()
        r = sommeil.dernier_resume("A", racine=self.racine)
        self.assertEqual(r["date"], JOUR_1.isoformat())
        self.assertEqual(r["stats"]["notes"], 3)
        self.assertEqual(r["stats"]["notes_sensibles"], 1)
        self.assertEqual(r["stats"]["taches_a_faire"], 1)
        self.assertIn("3 note(s)", r["resume"])
        self.assertEqual(bilan["projets"]["A"]["resume"], r["resume"])
        journal = [l["evenement"] for l in projets.lire_journal("A", racine=self.racine)]
        self.assertIn("sommeil · analyse (résumé)", journal)

    def test_note_sensible_jamais_dans_la_demande(self):
        self.dormir()
        texte = json.dumps(self.demandes("resumer"), ensure_ascii=False)
        self.assertNotIn("9876", texte)
        self.assertNotIn("Privé", texte)
        self.assertIn("Budget", texte)

    def test_limite_de_jetons_respectee(self):
        for i in range(30):
            cc.creer_note_humaine("A", f"Note longue {i}", "blabla " * 80, date=JOUR_1,
                                  racine=self.racine)
        (self.racine / "reglages.local").write_text("ANALYSE_MAX_TOKENS=300\n")
        self.dormir()
        envoye = json.dumps(self.demandes("resumer")[0], ensure_ascii=False)
        self.assertLessEqual(len(envoye), 300 * 4)
        self.assertLessEqual(sommeil.dernier_resume("A", racine=self.racine)["jetons_envoyes"], 300)
        # Les statistiques du projet entier restent présentes même si les notes sont coupées.
        self.assertEqual(self.demandes("resumer")[0]["statistiques"]["notes"], 33)
