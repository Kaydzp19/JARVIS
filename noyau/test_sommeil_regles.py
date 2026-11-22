"""
Tests de la marche 6, partie 8 : les règles du sommeil et du rêve.
"""

import hashlib
import json

from noyau import corps_calleux as cc
from noyau import projets, routeur_ia, sommeil, systeme
from noyau.base_tests import JOUR_1, TestTemporaire
from noyau.test_sommeil_tri import Espion


class FauxGeminiGratuit(routeur_ia.Fournisseur):
    """Une offre gratuite en ligne, branchée pour le test : elle garde tout ce qu'elle reçoit."""
    nom = "gemini"
    gratuit = True
    branche = True

    def __init__(self):
        self.recus = []

    def repondre(self, tache, texte, temperature=None):
        self.recus.append(texte)
        return "réponse libre, sans JSON"


class TestRegles(TestTemporaire):

    def setUp(self):
        super().setUp()
        for p in ("A", "B"):
            projets.creer_projet(p, racine=self.racine)
            for t in ("Un", "Deux", "Trois", "Quatre"):
                cc.creer_note_humaine(p, f"{t} {p}", f"Contenu {t} du projet {p}.", date=JOUR_1,
                                      racine=self.racine)
        cc.creer_note_humaine("A", "Coffre", "Combinaison 5555.", sensible=True, date=JOUR_1,
                              racine=self.racine)

    def empreinte_des_notes(self):
        h = hashlib.sha256()
        for p in ("A", "B"):
            for n in projets.lister_notes(p, racine=self.racine):
                h.update(projets.lire_note(p, n["id"], racine=self.racine).encode())
                h.update(str(n["validee"]).encode())
        return h.hexdigest()

    def test_pas_de_plafond_propre_au_reve(self):
        # 4 appels à 0,02 € : plus que l'ancien plafond de 0,03 €, et pourtant tout passe.
        bilan = sommeil.dormir(JOUR_1, projet="A", racine=self.racine,
                               fournisseurs={"demo": Espion(cout_par_appel=0.02)})
        self.assertIsNone(bilan["arret"])
        self.assertGreater(bilan["cout"], 0.03)

    def test_budget_mensuel_epuise_arret_propre(self):
        # Seule limite : le compteur de coûts GLOBAL du routeur (5 € par mois par défaut).
        bilan = sommeil.dormir(JOUR_1, racine=self.racine,
                               fournisseurs={"demo": Espion(cout_par_appel=3.0)})
        self.assertIn("Plafond IA atteint", bilan["arret"])
        self.assertEqual(list(bilan["projets"]), ["A"])  # B n'est pas entamé
        journal = [l["evenement"] for l in projets.lire_journal("A", racine=self.racine)]
        self.assertTrue(any(e.startswith("sommeil · arrêt propre") for e in journal))

    def test_sensible_jamais_vers_offre_gratuite(self):
        cc.marquer_projet_sensible("B", racine=self.racine)
        gemini = FauxGeminiGratuit()
        sommeil.dormir(JOUR_1, racine=self.racine,
                       fournisseurs={"demo": routeur_ia.IADemo(), "gemini": gemini})
        tout = " ".join(gemini.recus)
        self.assertTrue(gemini.recus)            # le projet A (non sensible) y est allé
        self.assertNotIn("5555", tout)           # note sensible de A : jamais
        self.assertNotIn("Coffre", tout)
        self.assertNotIn("projet B", tout)       # projet B sensible : jamais
        self.assertNotIn("Un B", tout)

    def test_tout_passe_par_le_routeur(self):
        bilan = sommeil.dormir(JOUR_1, racine=self.racine)
        conn = systeme.connexion(self.racine)
        try:
            notes = conn.execute("SELECT COUNT(*) FROM appels_ia WHERE statut = 'ok'").fetchone()[0]
            taches = {r[0] for r in conn.execute("SELECT DISTINCT tache FROM appels_ia")}
        finally:
            conn.close()
        self.assertEqual(notes, bilan["appels_ia"])
        self.assertTrue({"trier", "resumer", "rever", "evaluer"} <= taches)

    def test_le_reve_ne_fait_que_proposer(self):
        avant = self.empreinte_des_notes()
        nb_avant = sum(len(projets.lister_notes(p, racine=self.racine)) for p in ("A", "B"))
        sommeil.dormir(JOUR_1, racine=self.racine)
        self.assertEqual(self.empreinte_des_notes(), avant)
        self.assertEqual(sum(len(projets.lister_notes(p, racine=self.racine)) for p in ("A", "B")),
                         nb_avant)

    def test_reponse_illisible_sans_plantage(self):
        gemini = FauxGeminiGratuit()
        bilan = sommeil.dormir(JOUR_1, projet="A", racine=self.racine,
                               fournisseurs={"gemini": gemini})
        self.assertIsNone(bilan["arret"])
        self.assertIsNone(bilan["projets"]["A"]["reve"])

    def test_chaque_phase_ecrit_au_journal(self):
        sommeil.dormir(JOUR_1, projet="A", racine=self.racine)
        evenements = [l["evenement"] for l in projets.lire_journal("A", racine=self.racine)]
        for prefixe in ("sommeil · tri (code)", "sommeil · tri (IA)", "sommeil · analyse (résumé)",
                        "sommeil · analyse (synthèses)", "sommeil · rêve", "sommeil · réveil",
                        "sommeil terminé"):
            self.assertTrue(any(e.startswith(prefixe) for e in evenements), prefixe)
        self.assertTrue(json.dumps(evenements, ensure_ascii=False))
