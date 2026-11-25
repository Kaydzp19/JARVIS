"""
Tests de la démo en ligne (dossier vercel-demo/, site statique pour Vercel).

1. Le site contient exactement le cockpit de interface/sphere/, en mode « démo en ligne ».
2. Aucune clé, aucun chemin local, aucun fichier de test publié.
3. vercel.json sert le dossier tel quel, sans construction.
"""

import json
import re
import sys
from pathlib import Path

RACINE_DEPOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE_DEPOT / "exemples"))

import export_demo  # noqa: E402
from noyau.base_tests import TestTemporaire  # noqa: E402

SITE = RACINE_DEPOT / "vercel-demo"


class TestDemoEnLigne(TestTemporaire):

    def test_site_a_jour(self):
        neuf = Path(self.racine) / "site"
        export_demo.construire_sphere(destination=neuf)
        publies = sorted(f.relative_to(SITE) for f in SITE.rglob("*") if f.is_file())
        attendus = sorted(f.relative_to(neuf) for f in neuf.rglob("*") if f.is_file())
        self.assertEqual(publies, attendus, "Relance : python3 exemples/export_demo.py")
        for rel in attendus:
            self.assertEqual((neuf / rel).read_bytes(), (SITE / rel).read_bytes(),
                             f"{rel} n'est pas à jour : relance python3 exemples/export_demo.py")

    def test_mode_demo_en_ligne(self):
        index = (SITE / "index.html").read_text(encoding="utf-8")
        for attendu in ('data-mode="demo-en-ligne"', "/sphere/js/main.js", "#010409", "three@0.160.0",
                        "Démo · données fictives"):
            self.assertIn(attendu, index)
        self.assertIn('data-mode="demo-en-ligne"', (SITE / "sphere" / "catalogue.html").read_text(encoding="utf-8"))
        self.assertFalse((SITE / "sphere" / "tests").exists())

    def test_sans_cle_ni_chemin(self):
        for f in sorted(SITE.rglob("*")):
            if f.is_file():
                texte = f.read_text(encoding="utf-8")
                m = re.search(r"(sk-ant|sk-[A-Za-z0-9]{10,}|AIza[0-9A-Za-z_-]{10,}|/Users/|/home/|"
                              r"reglages\.local|projet\.db|\.jarvis/)", texte)
                self.assertIsNone(m, f"{f.name} : {m.group(0) if m else ''}")

    def test_vercel_json(self):
        conf = json.loads((RACINE_DEPOT / "vercel.json").read_text(encoding="utf-8"))
        self.assertEqual(conf["outputDirectory"], "vercel-demo")
        self.assertIsNone(conf["framework"])
        self.assertNotIn("buildCommand", conf)
        self.assertNotIn("redirects", conf)
