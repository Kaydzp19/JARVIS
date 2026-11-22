"""
Tests de la marche 6, parties 4 à 7 : rêve, réveil, stockage, apprentissage.
"""

import json
from datetime import timedelta

from noyau import corps_calleux as cc
from noyau import projets, reve, sommeil
from noyau.base_tests import JOUR_1, TestTemporaire
from noyau.test_sommeil_tri import Espion


class BaseReve(TestTemporaire):

    def setUp(self):
        super().setUp()
        projets.creer_projet("A", racine=self.racine)
        self.espion = Espion()
        n = lambda t, x, **k: cc.creer_note_humaine("A", t, x, date=JOUR_1, racine=self.racine, **k)
        self.cuisine = n("Recettes", "Cuisiner des plats simples le dimanche.")
        self.vente = n("Clients", "Trouver des clients dans le quartier. Voir [[Prix]].")
        self.prix = n("Prix", "Fixer un prix clair. Voir [[Clients]].")
        self.sport = n("Course à pied", "Courir trois fois par semaine.")
        self.lecture = n("Lecture", "Lire un livre par mois.")
        self.secret = n("Journal intime", "Mes pensées privées 4321.", sensible=True)

    def dormir(self, jours=0, **k):
        return sommeil.dormir(JOUR_1 + timedelta(days=jours), projet="A", racine=self.racine,
                              fournisseurs={"demo": self.espion}, **k)

    def demandes(self, tache):
        return [(json.loads(t), temp) for nom, t, temp in self.espion.recus if nom == tache]


class TestPhaseReve(BaseReve):

    def test_combinaisons_de_notes_eloignees_seulement(self):
        poids = reve.poids_entre("A", self.racine)
        notes = [n for n in cc.se_souvenir("A", "", 50, racine=self.racine) if not n["sensible"]]
        combos = reve.tirer_combinaisons(notes, poids, 6, 0.08, graine="x")
        self.assertTrue(combos)
        for c in combos:
            self.assertFalse({self.vente, self.prix} <= set(c), "Clients et Prix sont déjà liés")
            self.assertNotIn(self.secret, c)
        # Même graine (même projet, même nuit) : même tirage.
        self.assertEqual(combos, reve.tirer_combinaisons(notes, poids, 6, 0.08, graine="x"))

    def test_ia_creative_temperature_haute_et_cinq_idees(self):
        bilan = self.dormir()
        demande, temperature = self.demandes("rever")[0]
        self.assertEqual(temperature, 1.0)
        self.assertEqual(demande["nombre_idees"], 5)
        self.assertEqual(bilan["projets"]["A"]["idees_revees"], 5)

    def test_notes_sensibles_jamais_dans_le_reve(self):
        self.dormir()
        texte = json.dumps(self.demandes("rever"), ensure_ascii=False)
        self.assertNotIn("4321", texte)
        self.assertNotIn("Journal intime", texte)

    def test_pas_assez_de_notes(self):
        projets.creer_projet("B", racine=self.racine)
        cc.creer_note_humaine("B", "Seule", "x", date=JOUR_1, racine=self.racine)
        bilan = sommeil.dormir(JOUR_1, projet="B", racine=self.racine,
                               fournisseurs={"demo": self.espion})
        self.assertEqual(bilan["projets"]["B"]["idees_revees"], 0)
        self.assertEqual(self.demandes("rever"), [])


class TestPhaseReveil(BaseReve):

    def test_une_seule_idee_gardee_avec_ses_sources(self):
        bilan = self.dormir()
        rid = bilan["projets"]["A"]["reve"]
        self.assertIsNotNone(rid)
        tous = reve.lister("A", racine=self.racine)
        self.assertEqual(len(tous), 1)
        r = tous[0]
        self.assertEqual(r["id"], rid)
        self.assertEqual(r["statut"], "nouvelle")
        self.assertGreaterEqual(len(r["sources"]), 2)
        self.assertEqual(len(r["sources_titres"]), len(r["sources"]))
        self.assertTrue(r["raison"])
        self.assertEqual(r["details"]["idees_evaluees"], 5)
        demande, temperature = self.demandes("evaluer")[0]
        self.assertEqual(temperature, 0.2)  # IA rigoureuse
        self.assertEqual(len(demande["idees"]), 5)

    def test_une_seule_idee_par_nuit(self):
        self.dormir()
        bilan = self.dormir()  # même nuit, relancé à la main
        self.assertIsNone(bilan["projets"]["A"]["reve"])
        self.assertEqual(len(reve.lister("A", racine=self.racine)), 1)
        self.assertEqual(len(self.demandes("rever")), 1)  # pas de dépense inutile
        self.dormir(1)
        self.assertEqual(len(reve.lister("A", racine=self.racine)), 2)

    def test_contraintes_lues_dans_les_reglages(self):
        (self.racine / "reglages.local").write_text(
            "CONTRAINTE_BUDGET_EUR=0\nCONTRAINTE_NIVEAU=débutant\n"
            "CONTRAINTE_OBJECTIFS=trouver des clients, fixer un prix\n")
        self.dormir()
        demande, _ = self.demandes("evaluer")[0]
        self.assertEqual(demande["contraintes"]["objectifs"], "trouver des clients, fixer un prix")
        r = reve.lister("A", racine=self.racine)[0]
        # Budget 0 € : une idée payante n'est jamais faisable, donc jamais choisie.
        self.assertEqual(r["details"]["cout_estime_eur"], 0)
        self.assertNotEqual(r["details"]["effort"], "fort")

    def test_aucune_idee_si_toutes_mauvaises(self):
        bilan = sommeil.dormir(JOUR_1, projet="A", racine=self.racine,
                               fournisseurs={"demo": self.espion}, reglages={"score_min": 10.0})
        self.assertIsNone(bilan["projets"]["A"]["reve"])
        self.assertEqual(reve.lister("A", racine=self.racine), [])


class TestStockageEtCommandes(BaseReve):

    def jarvis(self, *args):
        import os
        import subprocess
        import sys
        from pathlib import Path
        depot = Path(__file__).resolve().parent.parent
        r = subprocess.run([sys.executable, str(depot / "jarvis.py"), *args], capture_output=True,
                           text=True, env=dict(os.environ), timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout

    def test_table_reves_et_statuts(self):
        self.dormir()
        r = reve.lister("A", racine=self.racine)[0]
        self.assertEqual(set(r) >= {"idee", "sources", "score", "statut", "raison"}, True)
        reve.rejeter("A", r["id"], "trop vague", date=JOUR_1, racine=self.racine)
        r = reve.lire("A", r["id"], racine=self.racine)
        self.assertEqual((r["statut"], r["raison"]), ("rejetée", "trop vague"))
        with self.assertRaises(ValueError):
            reve.changer_statut("A", r["id"], "inventé", racine=self.racine)

    def test_identifiants(self):
        self.dormir()
        projets.creer_projet("B", racine=self.racine)
        for t in ("Un", "Deux", "Trois"):
            cc.creer_note_humaine("B", t, f"Note {t} sur un sujet {t}.", date=JOUR_1,
                                  racine=self.racine)
        sommeil.dormir(JOUR_1, projet="B", racine=self.racine)
        self.assertEqual(reve.trouver("A:1", racine=self.racine), ("A", 1))
        with self.assertRaises(KeyError):
            reve.trouver("1", racine=self.racine)  # ambigu : A:1 et B:1
        with self.assertRaises(KeyError):
            reve.trouver("A:99", racine=self.racine)

    def test_commandes_jarvis_reve(self):
        self.dormir()
        sortie = self.jarvis("reve")
        self.assertIn("[A:1]", sortie)
        self.assertIn("sources :", sortie)
        sortie = self.jarvis("reve", "garder", "1", "bonne piste")
        self.assertIn("gardée", sortie)
        self.assertIn("Aucune nouvelle idée", self.jarvis("reve"))
        self.assertEqual(reve.lire("A", 1, racine=self.racine)["raison"], "bonne piste")


class TestApprentissage(BaseReve):

    def test_idee_gardee_renforce_ses_notes_sources(self):
        from noyau import synapses
        self.dormir()
        r = reve.lister("A", racine=self.racine)[0]
        a, b = r["sources"][:2]
        self.assertIsNone(synapses.synapse_entre("A", a, b, racine=self.racine))  # éloignées
        res = reve.garder("A", r["id"], "à creuser", date=JOUR_1, racine=self.racine)
        self.assertGreaterEqual(res["liens_crees"], 1)
        self.assertGreaterEqual(res["synapses_activees"], 1)
        sommeil.dormir(JOUR_1 + timedelta(days=1), projet="A", racine=self.racine,
                       fournisseurs={"demo": self.espion})
        poids = (synapses.synapse_entre("A", a, b, racine=self.racine)
                 or synapses.synapse_entre("A", b, a, racine=self.racine))["poids"]
        self.assertAlmostEqual(poids, 0.98 * 0.1 + 0.1)
        journal = [l["evenement"] for l in projets.lire_journal("A", racine=self.racine)]
        self.assertTrue(any("apprentissage : rêve n°" in e for e in journal))

    def test_note_non_validee_jamais_renforcee_par_un_reve(self):
        from noyau import synapses
        brouillon = projets.creer_note("A", "Brouillon IA", "Idée non relue.", racine=self.racine)
        bon = self.cuisine
        self.assertIsNone(synapses.creer_synapse("A", brouillon, bon, JOUR_1, racine=self.racine))

    def test_idee_rejetee_rappelee_et_pas_repetee(self):
        self.dormir()
        premiere = reve.lister("A", racine=self.racine)[0]
        reve.rejeter("A", premiere["id"], "pas le moment", date=JOUR_1, racine=self.racine)
        journal = projets.lire_journal("A", racine=self.racine)
        self.assertTrue(any(l["raison"] == "pas le moment" for l in journal))
        self.dormir(1)
        demande_reve, _ = self.demandes("rever")[-1]
        demande_eval, _ = self.demandes("evaluer")[-1]
        rappel = {"idee": premiere["idee"], "raison": "pas le moment"}
        self.assertIn(rappel, demande_reve["idees_rejetees"])
        self.assertIn(rappel, demande_eval["idees_rejetees"])
        seconde = reve.lister("A", racine=self.racine)[-1]
        self.assertNotEqual(seconde["idee"], premiere["idee"])
        from noyau.outils import similarite
        self.assertLess(similarite(seconde["idee"], premiere["idee"]), 0.6)
