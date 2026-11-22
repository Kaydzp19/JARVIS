"""
Tests de la marche 4 : routeur IA et budget.
"""

from datetime import date

from noyau import routeur_ia as r
from noyau.base_tests import JOUR_1, TestTemporaire


class FauxGemini(r.Fournisseur):
    """Simule un Gemini gratuit branché, pour vérifier qu'il n'est jamais choisi si sensible."""
    nom = "gemini"
    gratuit = True
    branche = True

    def __init__(self):
        self.appels = 0

    def repondre(self, tache, texte):
        self.appels += 1
        return "réponse de Gemini"


class TestRouteurIA(TestTemporaire):

    def test_une_question_recoit_une_reponse(self):
        res = r.demander_ia("question", "Bonjour JARVIS", date=JOUR_1, racine=self.racine)
        self.assertIn("Bonjour JARVIS", res["reponse"])
        self.assertEqual(res["fournisseur"], "demo")
        self.assertEqual(r.nombre_appels(self.racine), 1)

    def test_plafond_simule_bloque_l_appel(self):
        chere = {"demo": r.IADemo(cout_par_appel=2.0)}
        r.demander_ia("q", "1", date=JOUR_1, racine=self.racine, fournisseurs=chere, plafond=5)
        r.demander_ia("q", "2", date=JOUR_1, racine=self.racine, fournisseurs=chere, plafond=5)
        self.assertAlmostEqual(r.depense_du_mois(JOUR_1, self.racine), 4.0)
        with self.assertRaises(r.BudgetDepasse):
            r.demander_ia("q", "3", date=JOUR_1, racine=self.racine, fournisseurs=chere, plafond=5)
        self.assertAlmostEqual(r.depense_du_mois(JOUR_1, self.racine), 4.0)
        # Le mois suivant, le compteur repart de zéro.
        r.demander_ia("q", "4", date=date(2027, 2, 1), racine=self.racine,
                      fournisseurs=chere, plafond=5)

    def test_sensible_jamais_vers_offre_gratuite(self):
        gemini = FauxGemini()
        fournisseurs = {"demo": r.IADemo(), "gemini": gemini}
        normal = r.demander_ia("q", "x", racine=self.racine, fournisseurs=fournisseurs)
        self.assertEqual(normal["fournisseur"], "gemini")
        sensible = r.demander_ia("q", "x", sensible=True, racine=self.racine,
                                 fournisseurs=fournisseurs)
        self.assertEqual(sensible["fournisseur"], "demo")
        self.assertEqual(gemini.appels, 1)

    def test_fournisseurs_non_branches_ignores(self):
        # Sans code ni clé, Gemini et Claude ne sont jamais choisis.
        res = r.demander_ia("q", "x", difficulte="critique", racine=self.racine)
        self.assertEqual(res["fournisseur"], "demo")

    def test_plan_en_trois_etapes(self):
        res = r.demander_ia("planifier", "Écrire la page d'accueil", racine=self.racine)
        etapes = r.etapes_depuis_texte(res["reponse"])
        self.assertEqual(len(etapes), 3)
        self.assertTrue(all(e["duree_min"] > 0 for e in etapes))

    def test_plafond_lu_dans_les_reglages(self):
        (self.racine / "reglages.local").write_text("BUDGET_IA_MAX_EUR_MOIS=2,5\n")
        self.assertEqual(r.plafond_mensuel(), 2.5)
