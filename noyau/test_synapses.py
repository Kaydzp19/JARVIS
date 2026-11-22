"""
Tests de la marche 2 : synapses, renforcement et oubli.

Lancer depuis la racine du dépôt :
    python3 -m unittest noyau.test_synapses -v
Ou tous les tests (marches 1 et 2) :
    python3 -m unittest discover -s noyau -t . -v

Ces tests travaillent dans un dossier temporaire, supprimé à la fin.
Ils ne touchent JAMAIS au vrai dossier ~/.jarvis.
Les dates sont simulées (faux calendrier) : aucun test n'attend une vraie nuit.
"""

import os
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from noyau import projets, synapses

JOUR_1 = date(2027, 1, 1)


class BaseTest(unittest.TestCase):

    def setUp(self):
        self._temp = tempfile.TemporaryDirectory()
        self.racine = Path(self._temp.name)
        self._ancien = os.environ.get("DOSSIER_DONNEES")
        os.environ["DOSSIER_DONNEES"] = str(self.racine)

    def tearDown(self):
        if self._ancien is None:
            os.environ.pop("DOSSIER_DONNEES", None)
        else:
            os.environ["DOSSIER_DONNEES"] = self._ancien
        self._temp.cleanup()

    def note(self, projet, titre, contenu=""):
        return projets.creer_note(projet, titre, contenu, racine=self.racine)

    def lier(self, projet, note_id):
        return synapses.creer_synapses_de_note(projet, note_id, JOUR_1, racine=self.racine)

    def valider(self, projet, *ids):
        for i in ids:
            synapses.valider_note(projet, i, JOUR_1, racine=self.racine)

    def poids(self, projet, a, b):
        return synapses.synapse_entre(projet, a, b, racine=self.racine)["poids"]


class TestCreation(BaseTest):

    def test_un_lien_cree_une_synapse_a_0_1(self):
        projets.creer_projet("A", racine=self.racine)
        cible = self.note("A", "Cible")
        source = self.note("A", "Source", "voir [[Cible]] et [[Inconnue]]")
        crees = self.lier("A", source)
        self.assertEqual(len(crees), 1)  # [[Inconnue]] n'existe pas : ignoré
        s = synapses.synapse_entre("A", source, cible, racine=self.racine)
        self.assertAlmostEqual(s["poids"], 0.1)
        self.assertEqual(s["archivee"], 0)
        self.assertEqual(s["activations"], 0)

    def test_validee_vaut_0_par_defaut_puis_1(self):
        projets.creer_projet("A", racine=self.racine)
        n = self.note("A", "N")
        self.assertFalse(synapses.note_validee("A", n, racine=self.racine))
        self.valider("A", n)
        self.assertTrue(synapses.note_validee("A", n, racine=self.racine))


class TestRenforcementEtOubli(BaseTest):

    def setUp(self):
        super().setUp()
        projets.creer_projet("A", racine=self.racine)
        # Deux paires de notes reliées par un lien [[...]].
        self.c1 = self.note("A", "Cible 1")
        self.s1 = self.note("A", "Source 1", "[[Cible 1]]")
        self.c2 = self.note("A", "Cible 2")
        self.s2 = self.note("A", "Source 2", "[[Cible 2]]")
        self.lier("A", self.s1)
        self.lier("A", self.s2)

    # Test 1
    def test_1_notes_utilisees_ensemble_plus_fortes_le_lendemain(self):
        self.valider("A", self.c1, self.s1, self.c2, self.s2)
        self.assertTrue(synapses.utiliser_ensemble(
            "A", self.s1, self.c1, JOUR_1, racine=self.racine))
        synapses.appliquer_oubli("A", JOUR_1 + timedelta(days=1), racine=self.racine)

        utilisee = self.poids("A", self.s1, self.c1)
        pas_utilisee = self.poids("A", self.s2, self.c2)
        self.assertAlmostEqual(utilisee, 0.98 * 0.1 + 0.1)   # 0,198
        self.assertAlmostEqual(pas_utilisee, 0.98 * 0.1)     # 0,098
        self.assertGreater(utilisee, pas_utilisee)

        journal = projets.lire_journal("A", racine=self.racine)
        self.assertTrue(any("synapse renforcée" in l["evenement"] for l in journal))

    # Test 2
    def test_2_lien_jamais_utilise_baisse_puis_est_archive(self):
        poids_precedent = self.poids("A", self.s2, self.c2)
        jour = JOUR_1
        nuits = 0
        while True:
            jour += timedelta(days=1)
            nuits += 1
            synapses.appliquer_oubli("A", jour, racine=self.racine)
            s = synapses.synapse_entre("A", self.s2, self.c2, racine=self.racine)
            if s["archivee"]:
                break
            self.assertLess(s["poids"], poids_precedent)  # baisse chaque nuit
            poids_precedent = s["poids"]
            self.assertLess(nuits, 100, "la synapse aurait dû être archivée")

        self.assertLess(s["poids"], 0.05)
        self.assertEqual(nuits, 35)  # 0,1 × 0,98^35 ≈ 0,049
        journal = projets.lire_journal("A", racine=self.racine)
        self.assertTrue(any("synapse archivée" in l["evenement"] for l in journal))

    def test_2b_faux_calendrier_en_un_seul_appel(self):
        # 40 nuits d'un coup donnent le même résultat que 40 appels.
        bilan = synapses.appliquer_oubli("A", JOUR_1 + timedelta(days=40), racine=self.racine)
        self.assertEqual(bilan["archivees"], 2)
        self.assertEqual(synapses.lister_synapses("A", racine=self.racine,
                                                  avec_archivees=False), [])

    # Test 3
    def test_3_note_non_validee_ne_renforce_jamais(self):
        self.valider("A", self.c1)  # s1 n'est PAS validée
        for i in range(5):
            jour = JOUR_1 + timedelta(days=i)
            self.assertFalse(synapses.utiliser_ensemble(
                "A", self.s1, self.c1, jour, racine=self.racine))
        synapses.appliquer_oubli("A", JOUR_1 + timedelta(days=5), racine=self.racine)
        s = synapses.synapse_entre("A", self.s1, self.c1, racine=self.racine)
        self.assertEqual(s["activations"], 0)
        self.assertLess(s["poids"], 0.1)  # seulement l'oubli, aucun gain
        journal = projets.lire_journal("A", racine=self.racine)
        self.assertTrue(any("renforcement refusé" in l["evenement"] for l in journal))

    def test_plafond_jamais_depasse(self):
        self.valider("A", self.c1, self.s1)
        for i in range(60):
            synapses.utiliser_ensemble("A", self.s1, self.c1, JOUR_1 + timedelta(days=i),
                                       racine=self.racine)
        synapses.appliquer_oubli("A", JOUR_1 + timedelta(days=60), racine=self.racine)
        self.assertLessEqual(self.poids("A", self.s1, self.c1), 1.0)

    def test_reglages_modifiables(self):
        self.valider("A", self.c1, self.s1)
        synapses.utiliser_ensemble("A", self.s1, self.c1, JOUR_1, racine=self.racine)
        synapses.appliquer_oubli("A", JOUR_1 + timedelta(days=1), racine=self.racine,
                                 reglages={"apprentissage": 0.5, "oubli": 0.0})
        self.assertAlmostEqual(self.poids("A", self.s1, self.c1), 0.6)


class TestEtancheite(BaseTest):

    # Test 4
    def test_4_synapse_ne_traverse_jamais_deux_projets(self):
        projets.creer_projet("A", racine=self.racine)
        projets.creer_projet("B", racine=self.racine)
        self.note("B", "Seulement dans B")
        source_a = self.note("A", "Note A", "lien vers [[Seulement dans B]]")
        self.assertEqual(self.lier("A", source_a), [])
        self.assertEqual(synapses.lister_synapses("A", racine=self.racine), [])
        self.assertEqual(synapses.lister_synapses("B", racine=self.racine), [])

        # Même titre dans les deux projets : chaque lien reste chez lui.
        cible_a = self.note("A", "Commun")
        cible_b = self.note("B", "Commun")
        source_b = self.note("B", "Note B", "[[Commun]]")
        source_a2 = self.note("A", "Note A2", "[[Commun]]")
        self.lier("A", source_a2)
        self.lier("B", source_b)
        syn_a = synapses.lister_synapses("A", racine=self.racine)
        syn_b = synapses.lister_synapses("B", racine=self.racine)
        self.assertEqual([(s["note_source"], s["note_cible"]) for s in syn_a],
                         [(source_a2, cible_a)])
        self.assertEqual([(s["note_source"], s["note_cible"]) for s in syn_b],
                         [(source_b, cible_b)])
        ids_notes_a = {n["id"] for n in projets.lister_notes("A", racine=self.racine)}
        for s in syn_a:
            self.assertIn(s["note_source"], ids_notes_a)
            self.assertIn(s["note_cible"], ids_notes_a)


if __name__ == "__main__":
    unittest.main()


class TestLienVersNoteFuture(BaseTest):

    def test_lien_ecrit_avant_la_note_devient_une_synapse(self):
        projets.creer_projet("A", racine=self.racine)
        avant = self.note("A", "Plan", "Voir [[Budget]] (pas encore écrit)")
        self.assertEqual(self.lier("A", avant), [])
        budget = self.note("A", "Budget", "300")
        crees = synapses.relier_note("A", budget, JOUR_1, racine=self.racine)
        self.assertEqual(len(crees), 1)
        self.assertAlmostEqual(self.poids("A", avant, budget), 0.1)
        # Pas de doublon si on relie une seconde fois.
        self.assertEqual(synapses.relier_note("A", budget, JOUR_1, racine=self.racine), [])
