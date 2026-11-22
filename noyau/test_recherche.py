"""
Tests de la brique 1 (mémoire) : recherche plein texte FTS5.
"""

import sqlite3

from noyau import corps_calleux as cc
from noyau import projets, synapses
from noyau.base_tests import JOUR_1, TestTemporaire


class TestRecherche(TestTemporaire):

    def setUp(self):
        super().setUp()
        projets.creer_projet("A", racine=self.racine)
        projets.creer_projet("B", racine=self.racine)
        n = lambda p, t, x: cc.creer_note_humaine(p, t, x, date=JOUR_1, racine=self.racine)
        self.budget = n("A", "Budget", "Le budget prévisionnel est de trois cents euros.")
        self.evenement = n("A", "Lancement", "Un événement de lancement au marché couvert.")
        self.plan = n("A", "Plan", "Les étapes. Voir [[Budget]] et [[Lancement]].")
        n("B", "Budget B", "Un budget qui ne doit jamais sortir du projet B.")

    def test_trouve_dans_le_contenu(self):
        r = projets.rechercher("A", "prévisionnel", racine=self.racine)
        self.assertEqual([x["id"] for x in r], [self.budget])

    def test_sans_accents_ni_majuscules(self):
        r = projets.rechercher("A", "EVENEMENT", racine=self.racine)
        self.assertEqual(r[0]["id"], self.evenement)

    def test_prefixe(self):
        r = projets.rechercher("A", "lance", racine=self.racine)
        self.assertIn(self.evenement, [x["id"] for x in r])

    def test_le_titre_compte_plus(self):
        r = projets.rechercher("A", "budget", racine=self.racine)
        self.assertEqual(r[0]["id"], self.budget)  # « Budget » en titre devant « Plan » qui le cite

    def test_etancheite(self):
        r = projets.rechercher("A", "jamais sortir", racine=self.racine)
        self.assertEqual(r, [])

    def test_requete_dangereuse_sans_erreur(self):
        for q in ['"', "AND OR NOT", "budget*)(", "' ; DROP TABLE notes; --", ""]:
            projets.rechercher("A", q, racine=self.racine)  # ne doit jamais lever d'erreur

    def test_modification_reindexee(self):
        cc.modifier_note_humaine("A", self.plan, "Nouveau texte sur la météo.", date=JOUR_1,
                                 racine=self.racine)
        self.assertEqual([x["id"] for x in projets.rechercher("A", "météo", racine=self.racine)],
                         [self.plan])

    def test_index_reconstruit_pour_une_ancienne_base(self):
        db = projets.dossier_projet("A", self.racine) / "projet.db"
        with sqlite3.connect(db) as c:
            c.execute("DELETE FROM notes_fts")
        r = projets.rechercher("A", "prévisionnel", racine=self.racine)
        self.assertEqual([x["id"] for x in r], [self.budget])

    def test_se_souvenir_utilise_fts_et_synapses(self):
        r = cc.se_souvenir("A", "marché couvert", racine=self.racine)
        self.assertEqual(r[0]["id"], self.evenement)
        self.assertGreater(r[0]["pertinence"], 0)
        # À pertinence égale, la note la plus reliée passe devant.
        for s in synapses.lister_synapses("A", racine=self.racine):
            self.assertGreaterEqual(s["poids"], 0.1)
        r = cc.se_souvenir("A", "", racine=self.racine)
        self.assertEqual(r[0]["titre"], "Plan")  # 2 synapses : la plus reliée
