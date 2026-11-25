"""
Tests du contrat d'affichage (hologrammes) et de la trace de recherche.

- validation du schéma (scène, titre, données, contrôles, actions) ;
- application des événements, mettre_a_jour (même id, version + 1) ;
- garde d'écriture : une action d'écriture venue d'un widget n'est jamais exécutée ;
- trace de se_souvenir : identifiants, scores et liens, jamais le texte des notes.
"""

import json

from noyau import affichage
from noyau import corps_calleux as cc
from noyau import projets, synapses
from noyau.base_tests import JOUR_1, TestTemporaire


def evenement(**surcharge):
    ev = {"scene": "graphique", "titre": "Dépenses IA", "donnees": {"series": [1, 2, 3]}}
    ev.update(surcharge)
    return ev


class TestSchema(TestTemporaire):

    def test_evenement_minimal_valide(self):
        self.assertEqual(affichage.valider(evenement()), [])

    def test_scene_inconnue_acceptee(self):
        # L'interface affichera un widget générique : ce n'est pas une erreur.
        self.assertEqual(affichage.valider(evenement(scene="carte_du_monde")), [])

    def test_erreurs_de_forme(self):
        self.assertTrue(affichage.valider("texte"))
        self.assertTrue(affichage.valider(evenement(scene="Avec Espace")))
        self.assertTrue(affichage.valider(evenement(titre="")))
        self.assertTrue(affichage.valider(evenement(titre="x" * 121)))
        self.assertTrue(affichage.valider(evenement(donnees=[1, 2])))
        self.assertTrue(affichage.valider(evenement(inconnu=1)))
        self.assertTrue(affichage.valider(evenement(fermeture=-1)))

    def test_controles(self):
        ok = evenement(controles={"periode": ["24 h", "7 j", "6 mois"], "tri": ["score", "titre"]})
        self.assertEqual(affichage.valider(ok), [])
        self.assertTrue(affichage.valider(evenement(controles={"periode": ["1 siècle"]})))
        self.assertTrue(affichage.valider(evenement(controles={"zoom": ["x"]})))
        self.assertTrue(affichage.valider(evenement(controles={"tri": []})))

    def test_actions(self):
        ok = evenement(actions=[{"id": "ouvrir", "libelle": "Ouvrir"},
                                {"id": "noter", "libelle": "Noter", "type": "ecriture"}])
        self.assertEqual(affichage.valider(ok), [])
        self.assertTrue(affichage.valider(evenement(actions=[{"id": "Mauvais id", "libelle": "x"}])))
        self.assertTrue(affichage.valider(evenement(actions=[{"id": "a", "libelle": "x"},
                                                             {"id": "a", "libelle": "y"}])))
        self.assertTrue(affichage.valider(evenement(actions=[{"id": "a", "libelle": "x",
                                                              "type": "magie"}])))

    def test_aucun_texte_de_note(self):
        for cle in ("contenu", "texte", "extrait", "Contenu"):
            erreurs = affichage.valider(evenement(donnees={"notes": [{"titre": "x", cle: "y"}]}))
            self.assertTrue(erreurs, cle)
            self.assertIn("jamais", erreurs[0])

    def test_vue_transversale_en_lecture_seule(self):
        ev = evenement(projet="*", actions=[{"id": "supprimer", "libelle": "Supprimer"}])
        self.assertTrue(affichage.valider(ev))
        self.assertEqual(affichage.valider(evenement(projet="*")), [])

    def test_ecriture_reconnue_par_le_nom(self):
        for nom in ("supprimer", "publier", "payer", "ecrire_note", "envoyer"):
            self.assertTrue(affichage.est_ecriture({"id": nom}), nom)
        self.assertFalse(affichage.est_ecriture({"id": "periode"}))
        self.assertTrue(affichage.est_ecriture({"id": "x", "type": "ecriture"}))


class TestEvenements(TestTemporaire):

    def setUp(self):
        super().setUp()
        projets.creer_projet("A", racine=self.racine)

    def test_afficher_puis_lire_et_lister(self):
        ev = affichage.afficher("graphique", "Dépenses", {"series": [1]}, projet="A",
                                racine=self.racine)
        self.assertEqual(ev["version"], 1)
        self.assertEqual(affichage.lire(ev["id"], self.racine)["titre"], "Dépenses")
        self.assertEqual([e["id"] for e in affichage.lister(racine=self.racine)], [ev["id"]])
        self.assertEqual(affichage.lister(apres=ev["id"], racine=self.racine), [])
        journal = [l["evenement"] for l in projets.lire_journal("A", self.racine)]
        self.assertTrue(any("affichage" in l and "graphique" in l for l in journal))

    def test_afficher_refuse_un_evenement_invalide(self):
        with self.assertRaises(affichage.AffichageInvalide):
            affichage.afficher("notes_retenues", "Notes", {"notes": [{"contenu": "secret"}]},
                               racine=self.racine)
        self.assertEqual(affichage.lister(racine=self.racine), [])

    def test_mettre_a_jour_garde_le_meme_id(self):
        ev = affichage.afficher("graphique", "Dépenses", {"series": [1]}, racine=self.racine)
        maj = affichage.mettre_a_jour(ev["id"], {"series": [1, 2]}, racine=self.racine)
        self.assertEqual((maj["id"], maj["version"]), (ev["id"], 2))
        self.assertEqual(maj["donnees"], {"series": [1, 2]})
        with self.assertRaises(affichage.AffichageInvalide):
            affichage.mettre_a_jour(ev["id"], {"texte": "non"}, racine=self.racine)

    def test_action_de_lecture_met_a_jour(self):
        ev = affichage.afficher("graphique", "Dépenses", {"periode": "6 mois"}, projet="A",
                                controles={"periode": ["7 j", "6 mois"]}, racine=self.racine)
        vus = []

        def rafraichir(e, action, params):
            vus.append((e["id"], action, params))
            return {"periode": params["periode"]}

        r = affichage.recevoir_action(ev["id"], "periode", {"periode": "7 j"}, rafraichir,
                                      racine=self.racine)
        self.assertEqual(r["type"], "mise_a_jour")
        self.assertEqual(r["affichage"]["donnees"], {"periode": "7 j"})
        self.assertEqual(vus, [(ev["id"], "periode", {"periode": "7 j"})])
        self.assertEqual(affichage.actions_recues(ev["id"], self.racine)[0]["action"], "periode")

    def test_action_non_declaree_refusee(self):
        ev = affichage.afficher("graphique", "Dépenses", {}, racine=self.racine)
        with self.assertRaises(affichage.AffichageInvalide):
            affichage.recevoir_action(ev["id"], "lancer_fusee", {}, racine=self.racine)

    def test_garde_d_ecriture(self):
        notes_avant = projets.lister_notes("A", self.racine)
        ev = affichage.afficher("liste", "Tâches", {}, projet="A",
                                actions=[{"id": "supprimer", "libelle": "Supprimer la note"}],
                                racine=self.racine)
        appele = []
        r = affichage.recevoir_action(ev["id"], "supprimer", {"note": 3},
                                      lambda *a: appele.append(a), racine=self.racine)
        self.assertEqual(r["type"], "a_valider")
        self.assertEqual(appele, [])                           # rien n'est exécuté
        self.assertEqual(projets.lister_notes("A", self.racine), notes_avant)
        p = cc.lire_proposition("A", r["proposition"], self.racine)
        self.assertEqual(p["statut"], "en attente")
        self.assertIn("Supprimer la note", p["titre"])

    def test_ecriture_hors_projet_refusee(self):
        ev = affichage.afficher("liste", "Sans projet", {},
                                actions=[{"id": "publier", "libelle": "Publier"}], racine=self.racine)
        with self.assertRaises(PermissionError):
            affichage.recevoir_action(ev["id"], "publier", {}, racine=self.racine)
        tout = affichage.afficher("liste", "Tous les projets", {}, projet="*", racine=self.racine)
        with self.assertRaises(affichage.AffichageInvalide):     # non déclarée : refusée
            affichage.recevoir_action(tout["id"], "publier", {}, racine=self.racine)


class TestTrace(TestTemporaire):

    def setUp(self):
        super().setUp()
        projets.creer_projet("A", racine=self.racine)
        projets.creer_projet("B", racine=self.racine)
        n = lambda t, x, p="A": cc.creer_note_humaine(p, t, x, date=JOUR_1, racine=self.racine)
        self.ids = {
            "Clients": n("Clients", "Les clients cibles sont les artisans du quartier."),
            "Offre": n("Offre", "Une offre simple pour les clients. Voir [[Clients]]."),
            "Prix": n("Prix", "Le prix de l'offre est de 29 euros. Voir [[Offre]]."),
            "Lancement": n("Lancement", "Le lancement suit le [[Prix]] et l'[[Offre]]."),
            "Vacances": n("Vacances", "Partir en août à la montagne."),
        }
        n("Coffre", "Les clients de B ne doivent pas apparaître.", "B")

    def test_trace_sans_texte(self):
        t = cc.se_souvenir_trace("A", "prix des clients", racine=self.racine,
                                 aujourd_hui="2027-01-05")
        brut = json.dumps(t, ensure_ascii=False)
        for interdit in ("extrait", "contenu", "29 euros", "artisans", "montagne"):
            self.assertNotIn(interdit, brut)
        self.assertFalse(t["appel_ia"])
        self.assertEqual(t["notees"], 5)

    def test_trace_selection_et_chemins(self):
        t = cc.se_souvenir_trace("A", "prix", limite=3, racine=self.racine,
                                 aujourd_hui="2027-01-05")
        retenues = [r["id"] for r in t["retenues"]]
        self.assertEqual(retenues[0], self.ids["Prix"])
        self.assertLessEqual(len(retenues), 3)
        self.assertNotIn(self.ids["Vacances"], retenues)
        self.assertEqual(len(t["graines"]), 3)
        self.assertEqual([r["rang"] for r in t["retenues"]], list(range(1, len(retenues) + 1)))
        # Chaque synapse utilisée existe vraiment dans le projet.
        existantes = {(min(s["note_source"], s["note_cible"]), max(s["note_source"], s["note_cible"]))
                      for s in synapses.lister_synapses("A", self.racine)}
        for s in t["synapses"]:
            self.assertIn((s["a"], s["b"]), existantes)

    def test_trace_etanche_et_n_ecrit_rien(self):
        avant = len(projets.lire_journal("A", self.racine))
        t = cc.se_souvenir_trace("A", "clients", racine=self.racine)
        self.assertEqual(len(projets.lire_journal("A", self.racine)), avant)
        self.assertNotIn("Coffre", [r["titre"] for r in t["retenues"]])

    def test_trace_projet_vide(self):
        projets.creer_projet("Vide", racine=self.racine)
        t = cc.se_souvenir_trace("Vide", "x", racine=self.racine)
        self.assertEqual((t["retenues"], t["synapses"]), ([], []))
