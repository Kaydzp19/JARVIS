"""
Tests de la garde d'écriture : python -m noyau.valider <id>.
"""

import os
import subprocess
import sys
from pathlib import Path

from noyau import corps_calleux as cc
from noyau import projets
from noyau.base_tests import JOUR_1, TestTemporaire

RACINE_DEPOT = Path(__file__).resolve().parent.parent


class TestValider(TestTemporaire):

    def setUp(self):
        super().setUp()
        projets.creer_projet("Projet A", racine=self.racine)
        projets.creer_projet("Projet B", racine=self.racine)
        cc.creer_note_humaine("Projet A", "Plan", "Le plan.", date=JOUR_1, racine=self.racine)
        self.pa = cc.proposer("Projet A", "note", "# Idée A\nUne idée pour le [[Plan]].",
                              racine=self.racine)
        self.pb = cc.proposer("Projet B", "tache", "Appeler le fournisseur", racine=self.racine)

    def lancer(self, *args):
        r = subprocess.run([sys.executable, "-m", "noyau.valider", *args], cwd=str(RACINE_DEPOT),
                           capture_output=True, text=True, env=dict(os.environ), timeout=60)
        return r.returncode, r.stdout

    def test_liste_des_propositions(self):
        code, sortie = self.lancer()
        self.assertEqual(code, 0)
        self.assertIn("[Projet A:1]", sortie)
        self.assertIn("[Projet B:1]", sortie)

    def test_rien_n_est_ecrit_avant_la_validation(self):
        self.assertEqual(len(projets.lister_notes("Projet A", racine=self.racine)), 1)
        code, sortie = self.lancer("Projet A:1")
        self.assertEqual(code, 0, sortie)
        self.assertIn("validée et écrite", sortie)
        self.assertEqual(len(projets.lister_notes("Projet A", racine=self.racine)), 2)
        self.assertEqual(cc.lire_proposition("Projet A", self.pa, racine=self.racine)["statut"],
                         "validée")

    def test_numero_ambigu_refuse(self):
        code, sortie = self.lancer("1")  # existe dans A et dans B
        self.assertEqual(code, 1)
        self.assertIn("plusieurs projets", sortie)
        self.assertEqual(len(projets.lister_notes("Projet A", racine=self.racine)), 1)

    def test_refuser(self):
        code, sortie = self.lancer("Projet B:1", "--refuser", "plus tard")
        self.assertEqual(code, 0)
        self.assertIn("refusée", sortie)
        self.assertEqual(projets.lister_taches("Projet B", racine=self.racine), [])
        journal = projets.lire_journal("Projet B", racine=self.racine)
        self.assertEqual(journal[-1]["raison"], "plus tard")

    def test_deja_traitee(self):
        self.lancer("Projet A:1")
        code, sortie = self.lancer("Projet A:1")
        self.assertEqual(code, 1)
        self.assertIn("déjà", sortie)

    def test_inconnue(self):
        code, sortie = self.lancer("Projet A:99")
        self.assertEqual(code, 1)

    def test_projet_inconnu_message_clair(self):
        code, sortie = self.lancer("Projet Z:1")
        self.assertEqual(code, 1)
        self.assertIn("n'existe pas", sortie)
        self.assertNotIn("Traceback", sortie)

    def test_dossier_sans_projet(self):
        vide = self.racine / "vide"
        code, sortie = self.lancer("--dossier", str(vide))
        self.assertEqual(code, 1)
        self.assertIn("Aucun projet", sortie)
        self.assertIn("exemples/demo.py", sortie)
