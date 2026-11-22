"""
Tests de la marche 1 : projets étanches.

Lancer depuis la racine du dépôt :
    python3 -m unittest noyau.test_projets -v

Ces tests travaillent dans un dossier temporaire, supprimé à la fin.
Ils ne touchent JAMAIS au vrai dossier ~/.jarvis.
"""

import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

from noyau import projets


class TestProjets(unittest.TestCase):

    def setUp(self):
        self._temp = tempfile.TemporaryDirectory()
        self.racine = Path(self._temp.name)
        # Sécurité : si un appel oubliait « racine », il tomberait quand même
        # dans le dossier temporaire et non dans ~/.jarvis.
        self._ancien = os.environ.get("DOSSIER_DONNEES")
        os.environ["DOSSIER_DONNEES"] = str(self.racine)

    def tearDown(self):
        if self._ancien is None:
            os.environ.pop("DOSSIER_DONNEES", None)
        else:
            os.environ["DOSSIER_DONNEES"] = self._ancien
        self._temp.cleanup()

    # --- a) et b) création d'un projet ---

    def test_creer_projet_cree_dossiers_et_tables(self):
        dossier = projets.creer_projet("A", racine=self.racine)
        self.assertTrue((dossier / "notes").is_dir())
        self.assertTrue((dossier / "projet.db").is_file())
        with sqlite3.connect(dossier / "projet.db") as conn:
            tables = {r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}
        conn.close()
        self.assertTrue({"notes", "taches", "journal"} <= tables)

    def test_projet_deja_existant_refuse(self):
        projets.creer_projet("A", racine=self.racine)
        with self.assertRaises(FileExistsError):
            projets.creer_projet("A", racine=self.racine)

    def test_nom_de_projet_dangereux_refuse(self):
        for nom in ["", "..", "../evasion", "a/b", ".cache"]:
            with self.assertRaises(ValueError):
                projets.creer_projet(nom, racine=self.racine)

    # --- f) journal ---

    def test_creation_projet_ecrit_dans_le_journal(self):
        projets.creer_projet("A", racine=self.racine, acteur="kayd", raison="essai")
        journal = projets.lire_journal("A", racine=self.racine)
        self.assertEqual(len(journal), 1)
        self.assertIn("projet créé", journal[0]["evenement"])
        self.assertEqual(journal[0]["acteur"], "kayd")
        self.assertEqual(journal[0]["raison"], "essai")

    # --- c) notes ---

    def test_creer_note_ecrit_fichier_et_ligne(self):
        projets.creer_projet("A", racine=self.racine)
        nid = projets.creer_note("A", "Ma note", "Bonjour", racine=self.racine, sensible=True)
        notes = projets.lister_notes("A", racine=self.racine)
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0]["titre"], "Ma note")
        self.assertEqual(notes[0]["sensible"], 1)
        fichier = self.racine / "projets" / "A" / notes[0]["chemin"]
        self.assertTrue(fichier.is_file())
        self.assertEqual(fichier.suffix, ".md")
        self.assertEqual(projets.lire_note("A", nid, racine=self.racine), "Bonjour")

    def test_deux_notes_meme_titre_ne_s_ecrasent_pas(self):
        projets.creer_projet("A", racine=self.racine)
        n1 = projets.creer_note("A", "Idée", "un", racine=self.racine)
        n2 = projets.creer_note("A", "Idée", "deux", racine=self.racine)
        self.assertEqual(projets.lire_note("A", n1, racine=self.racine), "un")
        self.assertEqual(projets.lire_note("A", n2, racine=self.racine), "deux")

    # --- d) liens [[...]] ---

    def test_liens_reperes_dans_une_note(self):
        projets.creer_projet("A", racine=self.racine)
        nid = projets.creer_note(
            "A", "Plan",
            "Voir [[Budget 2027]] et [[Idées]], puis encore [[Budget 2027]].",
            racine=self.racine)
        self.assertEqual(projets.liens_de_note("A", nid, racine=self.racine),
                         ["Budget 2027", "Idées"])

    def test_texte_sans_lien(self):
        self.assertEqual(projets.trouver_liens("Pas de lien [ici] ni [[ ]]."), [])

    # --- Test de réussite : étanchéité entre A et B ---

    def test_projets_A_et_B_etanches(self):
        projets.creer_projet("A", racine=self.racine)
        projets.creer_projet("B", racine=self.racine)
        na = projets.creer_note("A", "Note de A", "secret A", racine=self.racine)
        nb = projets.creer_note("B", "Note de B", "secret B", racine=self.racine)
        projets.creer_tache("A", "Tâche de A", note_id=na, racine=self.racine)
        projets.creer_tache("B", "Tâche de B", note_id=nb, racine=self.racine)

        notes_a = [n["titre"] for n in projets.lister_notes("A", racine=self.racine)]
        notes_b = [n["titre"] for n in projets.lister_notes("B", racine=self.racine)]
        taches_a = [t["titre"] for t in projets.lister_taches("A", racine=self.racine)]
        taches_b = [t["titre"] for t in projets.lister_taches("B", racine=self.racine)]

        self.assertEqual(notes_a, ["Note de A"])
        self.assertEqual(notes_b, ["Note de B"])
        self.assertEqual(taches_a, ["Tâche de A"])
        self.assertEqual(taches_b, ["Tâche de B"])

        # Les fichiers de notes sont dans des dossiers séparés.
        fichiers_a = os.listdir(self.racine / "projets" / "A" / "notes")
        fichiers_b = os.listdir(self.racine / "projets" / "B" / "notes")
        self.assertEqual(fichiers_a, ["Note-de-A.md"])
        self.assertEqual(fichiers_b, ["Note-de-B.md"])

        # Le journal de A ne parle pas de B (et inversement).
        journal_a = " ".join(l["evenement"] for l in projets.lire_journal("A", racine=self.racine))
        journal_b = " ".join(l["evenement"] for l in projets.lire_journal("B", racine=self.racine))
        self.assertNotIn("de B", journal_a)
        self.assertNotIn("de A", journal_b)

        self.assertEqual(projets.lister_projets(racine=self.racine), ["A", "B"])

    def test_projet_inexistant_refuse(self):
        with self.assertRaises(FileNotFoundError):
            projets.lister_notes("Fantome", racine=self.racine)

    # --- Sécurité : le vrai ~/.jarvis n'est pas utilisé ---

    def test_racine_par_defaut_suit_dossier_donnees(self):
        self.assertEqual(projets.racine_par_defaut(), self.racine)


if __name__ == "__main__":
    unittest.main()
