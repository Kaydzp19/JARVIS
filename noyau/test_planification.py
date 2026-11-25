"""
Tests de la planification : table taches, récurrence, journal, garde d'écriture.
"""

from datetime import date

from noyau import corps_calleux as cc
from noyau import planification as pl
from noyau import projets
from noyau.base_tests import TestTemporaire


class TestRecurrence(TestTemporaire):

    def test_suites(self):
        def premieres(ancre, rec, n=4):
            it = pl.suite(ancre, rec)
            return [next(it).isoformat() for _ in range(n)]
        self.assertEqual(premieres("2027-01-30", "quotidienne"),
                         ["2027-01-30", "2027-01-31", "2027-02-01", "2027-02-02"])
        self.assertEqual(premieres("2027-01-01", "hebdomadaire", 3), ["2027-01-01", "2027-01-08", "2027-01-15"])
        # Vendredi 1er janvier 2027 : on saute le week-end.
        self.assertEqual(premieres("2027-01-01", "jours_ouvres"),
                         ["2027-01-01", "2027-01-04", "2027-01-05", "2027-01-06"])
        # Le 31 reste le 31 (ou le dernier jour du mois), sans dériver.
        self.assertEqual(premieres("2027-01-31", "mensuelle", 4),
                         ["2027-01-31", "2027-02-28", "2027-03-31", "2027-04-30"])
        self.assertEqual(premieres("2028-01-31", "mensuelle", 2), ["2028-01-31", "2028-02-29"])

    def test_prochaine_et_occurrences(self):
        self.assertIsNone(pl.prochaine_date("2027-01-01", "aucune"))
        self.assertEqual(pl.prochaine_date("2027-02-28", "mensuelle", "2027-01-31"), date(2027, 3, 31))
        t = {"echeance": "2027-01-06", "recurrence": "quotidienne", "ancre": "2027-01-01"}
        self.assertEqual([d.day for d in pl.occurrences(t, "2027-01-01", "2027-01-08")], [6, 7, 8])
        samedi = {"echeance": "2027-01-02", "recurrence": "jours_ouvres", "ancre": "2027-01-02"}
        self.assertEqual([d.day for d in pl.occurrences(samedi, "2027-01-01", "2027-01-05")], [2, 4, 5])


class TestTaches(TestTemporaire):

    def setUp(self):
        super().setUp()
        projets.creer_projet("A", racine=self.racine)
        projets.creer_projet("B", racine=self.racine)
        self.note = cc.creer_note_humaine("A", "Budget", "Trois cents euros.", racine=self.racine)

    def journal(self, projet="A"):
        return [l["evenement"] for l in projets.lire_journal(projet, self.racine)]

    def test_table_taches_nouvelles_colonnes(self):
        tid = pl.creer("A", {"titre": "Appeler le client", "date": "2027-01-04", "heure": "09:30",
                             "duree": 45, "priorite": "haute", "recurrence": "hebdomadaire",
                             "rappel": 15, "note_id": self.note}, racine=self.racine)
        t = pl.lire("A", tid, self.racine)
        self.assertEqual((t["echeance"], t["heure"], t["duree"], t["priorite"], t["recurrence"],
                          t["rappel"], t["note_id"], t["ancre"], t["statut"]),
                         ("2027-01-04", "09:30", 45, "haute", "hebdomadaire", 15, self.note,
                          "2027-01-04", "à faire"))
        self.assertTrue(any("créée : Appeler le client (2027-01-04 09:30)" in e for e in self.journal()))

    def test_validation(self):
        for mauvais in ({"titre": ""}, {"titre": "x", "heure": "25:00"}, {"titre": "x", "date": "demain"},
                        {"titre": "x", "duree": 2}, {"titre": "x", "priorite": "urgente"},
                        {"titre": "x", "recurrence": "annuelle"}, {"titre": "x", "recurrence": "quotidienne"},
                        {"titre": "x", "inconnu": 1}, {"titre": "x", "rappel": -5}):
            with self.assertRaises(pl.TacheInvalide, msg=str(mauvais)):
                pl.creer("A", mauvais, racine=self.racine)
        cc.creer_note_humaine("B", "Autre", "…", racine=self.racine)
        nb = cc.creer_note_humaine("B", "Encore", "…", racine=self.racine)   # n° 2 : absent de A
        with self.assertRaises(pl.TacheInvalide):           # étanchéité : note d'un autre projet
            pl.creer("A", {"titre": "x", "note_id": nb}, racine=self.racine)

    def test_modifier_deplacer_supprimer_journalises(self):
        tid = pl.creer("A", {"titre": "Écrire", "date": "2027-01-04", "heure": "10:00"}, racine=self.racine)
        pl.modifier("A", tid, {"date": "2027-01-05", "heure": "14:15"}, racine=self.racine)
        t = pl.lire("A", tid, self.racine)
        self.assertEqual((t["echeance"], t["heure"]), ("2027-01-05", "14:15"))
        self.assertTrue(any(f"tâche {tid} modifiée" in e and "14:15" in e for e in self.journal()))
        pl.supprimer("A", tid, racine=self.racine)
        with self.assertRaises(KeyError):
            pl.lire("A", tid, self.racine)
        self.assertTrue(any(f"tâche {tid} supprimée : Écrire" in e for e in self.journal()))

    def test_terminer_simple_et_recurrente(self):
        simple = pl.creer("A", {"titre": "Envoyer", "date": "2027-01-04"}, racine=self.racine)
        self.assertEqual(pl.terminer("A", simple, True, racine=self.racine)["statut"], "fait")
        self.assertEqual(pl.lire("A", simple, self.racine)["statut"], "fait")
        serie = pl.creer("A", {"titre": "Sport", "date": "2027-01-29", "recurrence": "jours_ouvres"},
                         racine=self.racine)
        r = pl.terminer("A", serie, False, racine=self.racine)
        self.assertEqual(r, {"statut": "pas fait", "prochaine": "2027-02-01"})   # vendredi → lundi
        t = pl.lire("A", serie, self.racine)
        self.assertEqual((t["echeance"], t["statut"]), ("2027-02-01", "à faire"))
        self.assertTrue(any("pas fait (occurrence du 2027-01-29), prochaine le 2027-02-01" in e
                            for e in self.journal()))

    def test_lister_et_prochaines(self):
        pl.creer("A", {"titre": "Quotidien", "date": "2027-01-04", "heure": "08:00",
                       "recurrence": "quotidienne"}, racine=self.racine)
        pl.creer("A", {"titre": "Sans date"}, racine=self.racine)
        pl.creer("B", {"titre": "Chez B", "date": "2027-01-05"}, racine=self.racine)
        l = pl.lister("A", "2027-01-04", 3, self.racine)
        self.assertEqual([(t["date"], t["occurrence"]) for t in l["taches"]],
                         [("2027-01-04", False), ("2027-01-05", True), ("2027-01-06", True)])
        self.assertEqual([t["titre"] for t in l["sans_date"]], ["Sans date"])
        self.assertNotIn("Chez B", str(l))                                   # étanchéité
        tous = pl.lister("*", "2027-01-04", 3, self.racine)
        self.assertIn("Chez B", [t["titre"] for t in tous["taches"]])
        p = pl.prochaines("*", 3, self.racine, aujourd_hui="2027-01-04")
        self.assertEqual([t["titre"] for t in p], ["Quotidien", "Chez B"])  # une fois par série

    def test_vue_transversale_en_lecture_seule(self):
        for faire in (lambda: pl.creer("*", {"titre": "x"}, racine=self.racine),
                      lambda: pl.modifier("*", 1, {"titre": "x"}, racine=self.racine),
                      lambda: pl.supprimer("*", 1, racine=self.racine),
                      lambda: pl.terminer("*", 1, True, racine=self.racine),
                      lambda: pl.proposer("*", {"titre": "x"}, racine=self.racine)):
            with self.assertRaises(PermissionError):
                faire()
        d = pl.donnees("*", "2027-01-04", "semaine", self.racine)
        self.assertTrue(d["lecture_seule"])
        self.assertEqual(d["notes"], [])

    def test_garde_d_ecriture_tache_proposee_par_jarvis(self):
        avant = len(projets.lister_taches("A", self.racine))
        pid = pl.proposer("A", {"titre": "Relancer le devis", "date": "2027-01-06", "heure": "11:00",
                                "duree": 20}, raison="idée du rêve", racine=self.racine)
        self.assertEqual(len(projets.lister_taches("A", self.racine)), avant)   # rien d'écrit
        self.assertEqual(cc.lire_proposition("A", pid, self.racine)["statut"], "en attente")
        tid = cc.valider_proposition("A", pid, racine=self.racine)
        t = pl.lire("A", tid, self.racine)
        self.assertEqual((t["titre"], t["echeance"], t["heure"], t["duree"]),
                         ("Relancer le devis", "2027-01-06", "11:00", 20))

    def test_donnees_sans_texte_de_note(self):
        from noyau import affichage
        pl.creer("A", {"titre": "Lire", "date": "2027-01-05", "note_id": self.note}, racine=self.racine)
        d = pl.donnees("A", "2027-01-06", "semaine", self.racine)
        self.assertEqual(d["debut"], "2027-01-04")                           # lundi
        self.assertEqual(d["taches"][0]["note_titre"], "Budget")
        self.assertNotIn("Trois cents", str(d))
        self.assertEqual(affichage.valider({"scene": "planification", "titre": "Planification",
                                            "donnees": d, "projet": "A"}), [])
