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
        self._environnement = dict(os.environ)  # tout l'environnement, remis à la fin
        os.environ["DOSSIER_DONNEES"] = str(self.racine)
        os.environ["JARVIS_REGLAGES"] = str(self.racine / "reglages.local")  # inexistant

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._environnement)
        self._temp.cleanup()
