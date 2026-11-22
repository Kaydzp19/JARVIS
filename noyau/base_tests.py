"""
Socle commun des tests : chaque test travaille dans un dossier temporaire,
supprimé à la fin. Le vrai ~/.jarvis et le vrai reglages.local ne sont
JAMAIS utilisés pendant les tests.
"""

import os
import tempfile
import unittest
from datetime import date
from pathlib import Path

JOUR_1 = date(2027, 1, 1)


class TestTemporaire(unittest.TestCase):

    def setUp(self):
        self._temp = tempfile.TemporaryDirectory()
        self.racine = Path(self._temp.name)
        self._anciens = {k: os.environ.get(k) for k in ("DOSSIER_DONNEES", "JARVIS_REGLAGES")}
        os.environ["DOSSIER_DONNEES"] = str(self.racine)
        os.environ["JARVIS_REGLAGES"] = str(self.racine / "reglages.local")  # inexistant

    def tearDown(self):
        for cle, valeur in self._anciens.items():
            if valeur is None:
                os.environ.pop(cle, None)
            else:
                os.environ[cle] = valeur
        self._temp.cleanup()
