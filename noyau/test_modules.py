"""
Tests de la marche 5B : modules (prises standard, modes DÉMO / RÉEL).
"""

import os
import shutil
from pathlib import Path

from noyau import modules, orchestrateur, projets
from noyau.base_tests import JOUR_1, TestTemporaire

RACINE_DEPOT = Path(__file__).resolve().parent.parent


class TestModules(TestTemporaire):

    def setUp(self):
        super().setUp()
        # On copie le module d'exemple dans un dossier temporaire pour pouvoir le retirer.
        self.dossier_modules = self.racine / "modules_installes"
        shutil.copytree(RACINE_DEPOT / "modules" / "notifications",
                        self.dossier_modules / "notifications")
        os.environ["JARVIS_MODULES"] = str(self.dossier_modules)
        projets.creer_projet("A", racine=self.racine)
        projets.creer_tache("A", "Tâche test", racine=self.racine)

    def tearDown(self):
        os.environ.pop("JARVIS_MODULES", None)
        super().tearDown()

    def boite(self):
        f = self.racine / "modules" / "notifications" / "boite.txt"
        return f.read_text(encoding="utf-8").splitlines() if f.exists() else []

    def test_module_decouvert_et_inactif_par_defaut(self):
        noms = [m["nom"] for m in modules.decouvrir()]
        self.assertEqual(noms, ["notifications"])
        self.assertFalse(modules.etat("notifications", self.racine)["actif"])
        orchestrateur.tour(JOUR_1, racine=self.racine)
        self.assertEqual(self.boite(), [])

    def test_activer_puis_retirer_sans_toucher_au_noyau(self):
        modules.activer("notifications", "DEMO", racine=self.racine)
        orchestrateur.tour(JOUR_1, racine=self.racine)
        self.assertEqual(len(self.boite()), 1)
        self.assertIn("Tâche test", self.boite()[0])
        journal = projets.lire_journal("A", racine=self.racine)
        self.assertTrue(any(l["acteur"] == "module:notifications" for l in journal))

        # Retrait : on supprime simplement le dossier du module.
        shutil.rmtree(self.dossier_modules / "notifications")
        self.assertEqual(modules.decouvrir(), [])
        projets.creer_tache("A", "Après retrait", racine=self.racine)
        bilan = orchestrateur.tour(JOUR_1, racine=self.racine)
        self.assertEqual(bilan["erreurs"], [])
        self.assertEqual(len(self.boite()), 1)  # plus de notification
        self.assertIsNotNone(orchestrateur.prochaine_action(racine=self.racine))

    def test_desactiver(self):
        modules.activer("notifications", "DEMO", racine=self.racine)
        modules.desactiver("notifications", racine=self.racine)
        orchestrateur.tour(JOUR_1, racine=self.racine)
        self.assertEqual(self.boite(), [])

    def test_mode_reel_exige_ses_reglages(self):
        with self.assertRaises(ValueError) as e:
            modules.activer("notifications", "REEL", racine=self.racine)
        self.assertIn("TELEGRAM_JETON", str(e.exception))

    def test_module_en_panne_ne_bloque_pas_le_noyau(self):
        casse = self.dossier_modules / "casse"
        casse.mkdir()
        (casse / "module.json").write_text(
            '{"nom": "casse", "evenements": ["contrat_pret"], "ecrit": []}')
        (casse / "module.py").write_text("def recevoir(e, d, c):\n    raise RuntimeError('boum')\n")
        modules.activer("casse", "DEMO", racine=self.racine)
        bilan = orchestrateur.tour(JOUR_1, racine=self.racine)
        self.assertEqual(bilan["erreurs"], [])
        self.assertEqual(len(bilan["actions"]), 1)
        r = modules.emettre("contrat_pret", {"projet": "A", "quoi": "x", "duree_totale_min": 1},
                            racine=self.racine)
        self.assertFalse(r[0]["ok"])

    def test_le_noyau_ne_cite_aucun_module(self):
        for fichier in (RACINE_DEPOT / "noyau").glob("*.py"):
            if fichier.name.startswith("test_"):
                continue
            texte = fichier.read_text(encoding="utf-8")
            # Une vraie dépendance : le nom du module comme chaîne exacte, un chemin ou un import.
            for signe in ('"notifications"', "'notifications'", "modules/notifications",
                          "modules.notifications", "import notifications"):
                self.assertNotIn(signe, texte, f"{fichier.name} dépend d'un module")
