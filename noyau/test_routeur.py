"""
Tests de la brique 3 : le routeur (entrée noyau/routeur.py).
"""

from datetime import date

from noyau import routeur
from noyau.base_tests import JOUR_1, TestTemporaire


class FauxGratuit(routeur.GeminiGratuit):
    """Une offre gratuite en ligne, branchée, qui garde tout ce qu'on lui envoie."""

    def __init__(self):
        self.recus = []

    def disponible(self):
        return True

    def repondre(self, tache, texte, temperature=None):
        self.recus.append(texte)
        return "réponse gratuite"


class FauxLocal(routeur.ModeleLocal):
    def __init__(self, pret=True):
        self.pret, self.recus = pret, []

    def disponible(self):
        return self.pret

    def repondre(self, tache, texte, temperature=None):
        self.recus.append(texte)
        return "réponse locale"


class TestRouteur(TestTemporaire):

    def test_mode_simule_par_defaut_sans_reseau(self):
        r = routeur.demander_ia("question", "courante", False, texte="Bonjour", racine=self.racine)
        self.assertEqual(r["fournisseur"], "demo")
        self.assertEqual(r["cout_estime"], 0)
        self.assertEqual(routeur.etat(self.racine)["mode"], "simule")

    def test_note_sensible_jamais_vers_une_offre_gratuite(self):
        gratuit = FauxGratuit()
        sans_local = {"gemini": gratuit, "local": FauxLocal(pret=False)}
        with self.assertRaises(routeur.AucuneIADisponible):
            routeur.demander_ia("resumer", "courante", True, texte="SECRET 1234",
                                racine=self.racine, fournisseurs=sans_local)
        self.assertEqual(gratuit.recus, [])  # PREUVE : rien n'est parti
        # Avec un modèle local prêt, la demande sensible y va, et seulement là.
        local = FauxLocal()
        r = routeur.demander_ia("resumer", "courante", True, texte="SECRET 1234",
                                racine=self.racine, fournisseurs={"gemini": gratuit, "local": local})
        self.assertEqual(r["fournisseur"], "local")
        self.assertEqual(gratuit.recus, [])
        self.assertEqual(local.recus, ["SECRET 1234"])

    def test_ordre_de_preference(self):
        gratuit, local = FauxGratuit(), FauxLocal()
        f = {"gemini": gratuit, "local": local}
        self.assertEqual(routeur.demander_ia("q", racine=self.racine, fournisseurs=f)["fournisseur"],
                         "local")
        f["local"] = FauxLocal(pret=False)
        self.assertEqual(routeur.demander_ia("q", racine=self.racine, fournisseurs=f)["fournisseur"],
                         "gemini")

    def test_plafond_5_euros_bloque(self):
        chere = {"demo": routeur.IADemo(cout_par_appel=1.0)}
        for _ in range(5):
            routeur.demander_ia("q", texte="x", date=JOUR_1, racine=self.racine, fournisseurs=chere)
        self.assertAlmostEqual(routeur.depense_du_mois(JOUR_1, self.racine), 5.0)
        with self.assertRaises(routeur.BudgetDepasse):
            routeur.demander_ia("q", texte="x", date=JOUR_1, racine=self.racine,
                                fournisseurs=chere)
        self.assertAlmostEqual(routeur.depense_du_mois(JOUR_1, self.racine), 5.0)
        self.assertEqual(routeur.plafond_mensuel(), 5.0)
        # Le mois suivant, le compteur repart.
        routeur.demander_ia("q", texte="x", date=date(2027, 2, 1), racine=self.racine,
                            fournisseurs=chere)

    def test_ollama_detecte_seulement(self):
        self.assertEqual(routeur.detecter_ollama()["pret"], False)  # « aucun » par défaut
        (self.racine / "reglages.local").write_text(
            "mode_ia=reel\nmodele_local=llama3.2\nollama_url=http://127.0.0.1:9\n")
        routeur.ModeleLocal._cache.clear()
        d = routeur.detecter_ollama()
        self.assertEqual((d["configure"], d["pret"]), ("llama3.2", False))
        e = routeur.etat(self.racine)
        self.assertEqual(e["mode"], "reel")
        self.assertFalse(e["gemini"]["cle"])
        self.assertEqual(e["budget"]["reste"], 5.0)
