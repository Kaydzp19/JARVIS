"""
Test de bout en bout de l'interface « sphère », dans un vrai navigateur (Playwright,
Chromium, WebGL logiciel). Long (environ 2 minutes) : lancé seulement sur demande.

    JARVIS_E2E=1 python3 -m unittest interface.test_e2e_sphere
    JARVIS_E2E=1 JARVIS_CAPTURES=docs/maquettes python3 -m unittest interface.test_e2e_sphere

Vérifie : une interaction par scène, la vague complète en 4 temps, la nuit en
4 phases, la garde d'écriture, l'iPhone (390 × 844), le mouvement réduit, le repli
sans WebGL, et aucune erreur dans la console. Données : démo dans un dossier temporaire.
"""

import json
import os
import shutil
import subprocess
import sys
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "exemples"))

import demo  # noqa: E402
from interface import serveur_web  # noqa: E402
from noyau.base_tests import TestTemporaire  # noqa: E402

SCRIPT = Path(__file__).resolve().parent / "sphere" / "tests" / "e2e_playwright.mjs"
NODE = shutil.which("node")


@unittest.skipUnless(os.environ.get("JARVIS_E2E") == "1" and NODE,
                     "Test navigateur : lance-le avec JARVIS_E2E=1 (Node.js et Playwright requis)")
class TestBoutEnBout(TestTemporaire):

    def test_interface_dans_le_navigateur(self):
        captures = os.environ.get("JARVIS_CAPTURES", "")
        os.environ["mode_ia"] = "simule"
        demo.creer_demo(racine=self.racine, bavard=False)
        serveur = serveur_web.creer_serveur(port=0, jeton="jeton-e2e", racine=self.racine)
        threading.Thread(target=serveur.serve_forever, daemon=True).start()
        try:
            if captures:
                Path(captures).mkdir(parents=True, exist_ok=True)
            r = subprocess.run([NODE, str(SCRIPT), f"http://127.0.0.1:{serveur.server_address[1]}",
                                "jeton-e2e"] + ([str(Path(captures).resolve())] if captures else []),
                               capture_output=True, text=True, timeout=600)
        finally:
            serveur.shutdown()
            serveur.server_close()
        self.assertEqual(r.returncode, 0, r.stderr[-3000:])
        bilan = json.loads(r.stdout.strip().splitlines()[-1])
        echecs = [f"{e['nom']} ({e['detail']})" for e in bilan["etapes"] if not e["ok"]]
        self.assertEqual(echecs, [])
        self.assertEqual(bilan["erreurs"], [])
        self.assertGreaterEqual(len(bilan["etapes"]), 60)
        print(f"\n{len(bilan['etapes'])} étapes réussies dans le navigateur, aucune erreur console.",
              file=sys.stderr)
