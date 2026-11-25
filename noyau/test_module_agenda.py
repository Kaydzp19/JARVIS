"""
Tests du module « agenda » (modules/agenda/) : mode DÉMO, lecture locale simulée,
masquage des titres, échec propre, écriture préparée mais jamais exécutée.
"""

import subprocess
from types import SimpleNamespace

from noyau import corps_calleux as cc
from noyau import modules, projets
from noyau.base_tests import TestTemporaire


def charger():
    conf = next(m for m in modules.decouvrir() if m["nom"] == "agenda")
    return conf, modules._charger_code(conf)


class TestModuleAgenda(TestTemporaire):

    def setUp(self):
        super().setUp()
        self.conf, self.code = charger()
        projets.creer_projet("A", racine=self.racine)

    def contexte(self, mode="DEMO"):
        return modules.Contexte(self.conf, mode, self.racine)

    def test_fiche_du_module(self):
        self.assertEqual(self.conf["demande"], [])               # aucun secret à fournir
        self.assertIn("agenda_lire", self.conf["evenements"])
        self.assertIn("propositions", self.conf["ecrit"])

    def test_mode_demo(self):
        r = self.code.recevoir("agenda_lire", {"debut": "2027-01-04", "fin": "2027-01-11"}, self.contexte())
        self.assertTrue(r["disponible"])
        self.assertEqual(len(r["evenements"]), 5)                 # jours ouvrés
        self.assertFalse(r["modifiable"])
        self.assertTrue(all(e["debut"].startswith("2027-01-") for e in r["evenements"]))

    def test_masquer_les_titres(self):
        import os
        os.environ["agenda_masquer_titres"] = "true"
        r = self.code.recevoir("agenda_lire", {"debut": "2027-01-04", "fin": "2027-01-05"}, self.contexte())
        self.assertEqual({e["titre"] for e in r["evenements"]}, {"occupé"})
        self.assertTrue(r["masque"])

    def test_lecture_locale_simulee(self):
        sortie = "Travail\x1fDentiste\x1f2027-01-04T14:00\x1f2027-01-04T14:45\x1ffalse\x1e"

        def executer(script):
            self.assertIn('tell application "Calendar"', script)
            self.assertIn("set year of dDebut to 2027", script)
            return SimpleNamespace(returncode=0, stdout=sortie, stderr="")
        r = self.code.lire_mac("2027-01-04", "2027-01-05", executer)
        self.assertEqual(r["evenements"], [{"calendrier": "Travail", "titre": "Dentiste",
                                            "debut": "2027-01-04T14:00", "fin": "2027-01-04T14:45",
                                            "journee": False}])

    def test_echec_propre(self):
        refus = lambda s: SimpleNamespace(returncode=1, stdout="", stderr="execution error: Not authorized (-1743)")
        r = self.code.lire_mac("2027-01-04", "2027-01-05", refus)
        self.assertFalse(r["disponible"])
        self.assertIn("Confidentialité", r["raison"])

        def lent(s):
            raise subprocess.TimeoutExpired("osascript", 30)
        self.assertFalse(self.code.lire_mac("2027-01-04", "2027-01-05", lent)["disponible"])

    def test_ecriture_preparee_jamais_executee(self):
        modules.activer("agenda", "DEMO", racine=self.racine)
        ev = {"titre": "Rendez-vous", "debut": "2027-01-05T10:00", "fin": "2027-01-05T11:00",
              "calendrier": "Perso"}
        r = modules.emettre("agenda_preparer_ecriture", {"projet": "A", "action": "creer", "evenement": ev},
                            racine=self.racine)[0]
        self.assertTrue(r["ok"], r)
        self.assertFalse(r["resultat"]["execute"])
        self.assertIn("make new event", r["resultat"]["script_prepare"])
        pid = r["resultat"]["proposition"]
        p = cc.lire_proposition("A", pid, self.racine)
        self.assertEqual(p["statut"], "en attente")
        self.assertEqual(p["details"]["module"], "agenda")
        avant = len(projets.lister_taches("A", self.racine))
        self.assertIsNone(cc.valider_proposition("A", pid, racine=self.racine))
        self.assertEqual(len(projets.lister_taches("A", self.racine)), avant)    # rien d'écrit ici
        journal = [l["raison"] or "" for l in projets.lire_journal("A", self.racine)]
        self.assertTrue(any("non exécuté" in j for j in journal))

    def test_le_planning_marche_sans_agenda(self):
        from interface import fournisseurs
        r = fournisseurs.calendrier("2027-01-04", 7, self.racine)        # module non activé
        self.assertFalse(r["disponible"])
        self.assertIn("modules --activer agenda", r["raison"])
        modules.activer("agenda", "DEMO", racine=self.racine)
        self.assertTrue(fournisseurs.calendrier("2027-01-04", 7, self.racine)["disponible"])
