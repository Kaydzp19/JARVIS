"""
Tests de la marche 6, partie A : réglages dans ~/.jarvis/ (hors du dépôt).
"""

import os
import subprocess
import sys
from pathlib import Path

from noyau import reglages
from noyau.base_tests import TestTemporaire

RACINE_DEPOT = Path(__file__).resolve().parent.parent


class TestReglages(TestTemporaire):

    def setUp(self):
        super().setUp()
        os.environ["JARVIS_REGLAGES"] = str(self.racine / "ancien" / "reglages.local")

    def test_valeurs_par_defaut(self):
        self.assertEqual(reglages.lire("idees_par_projet"), "1")
        self.assertEqual(reglages.lire("candidates_par_nuit"), "5")
        self.assertFalse(reglages.lire_booleen("cloud_pour_reveil"))
        self.assertEqual(reglages.lire("modele_local"), "aucun")
        self.assertEqual(reglages.lire_nombre("tokens_max_analyse", 0), 1500)
        self.assertEqual(reglages.lire("contrainte_niveau"), "débutant")

    def test_fichier_cree_dans_le_dossier_de_donnees_hors_depot(self):
        f = reglages.creer_fichier_si_absent()
        self.assertEqual(f, self.racine / "reglages.local")
        self.assertFalse(str(f).startswith(str(RACINE_DEPOT)))
        texte = f.read_text(encoding="utf-8")
        for cle in ("idees_par_projet=1", "candidates_par_nuit=5", "cloud_pour_reveil=false",
                    "modele_local=aucun", "tokens_max_analyse=", "contrainte_niveau=débutant",
                    "contrainte_objectifs="):
            self.assertIn(cle, texte)
        # Le fichier existant n'est jamais écrasé.
        f.write_text("idees_par_projet=2\n", encoding="utf-8")
        reglages.creer_fichier_si_absent()
        self.assertEqual(reglages.lire("idees_par_projet"), "2")

    def test_priorites(self):
        (self.racine / "ancien").mkdir()
        (self.racine / "ancien" / "reglages.local").write_text("candidates_par_nuit=7\n")
        self.assertEqual(reglages.lire("candidates_par_nuit"), "7")       # ancienne place
        (self.racine / "reglages.local").write_text("candidates_par_nuit=3\n")
        self.assertEqual(reglages.lire("candidates_par_nuit"), "3")       # ~/.jarvis gagne
        os.environ["candidates_par_nuit"] = "9"
        try:
            self.assertEqual(reglages.lire("candidates_par_nuit"), "9")   # environnement d'abord
        finally:
            del os.environ["candidates_par_nuit"]

    def test_booleens(self):
        for v, attendu in (("true", True), ("oui", True), ("1", True), ("false", False),
                           ("non", False)):
            (self.racine / "reglages.local").write_text(f"cloud_pour_reveil={v}\n")
            self.assertEqual(reglages.lire_booleen("cloud_pour_reveil"), attendu, v)

    def test_la_commande_cree_le_fichier(self):
        subprocess.run([sys.executable, str(RACINE_DEPOT / "jarvis.py"), "propositions"],
                       env=dict(os.environ), capture_output=True, timeout=60, check=True)
        self.assertTrue((self.racine / "reglages.local").exists())

    def test_le_modele_ne_contient_aucun_secret(self):
        for ligne in reglages.MODELE_FICHIER.splitlines():
            if ligne.startswith("# CLE_API"):
                self.assertTrue(ligne.endswith("="))
