"""
Tests de la marche 5 : orchestrateur, agents, voies, garde d'écriture.
"""

from noyau import agent as agents_mod
from noyau import corps_calleux as cc
from noyau import orchestrateur, projets, voies
from noyau.base_tests import JOUR_1, TestTemporaire


class TestOrchestrateur(TestTemporaire):

    def setUp(self):
        super().setUp()
        projets.creer_projet("A", racine=self.racine)
        projets.creer_projet("B", racine=self.racine)
        self.note = cc.creer_note_humaine("A", "Page d'accueil", "Texte de la page d'accueil.",
                                          date=JOUR_1, racine=self.racine)
        self.tache = projets.creer_tache("A", "Écrire le titre de la page d'accueil",
                                         note_id=self.note, echeance="2027-01-10",
                                         racine=self.racine)

    def test_une_tache_devient_un_ordre_complet(self):
        bilan = orchestrateur.tour(JOUR_1, racine=self.racine)
        self.assertEqual(bilan["erreurs"], [])
        c = orchestrateur.prochaine_action(racine=self.racine)
        self.assertEqual(c["quoi"], "Écrire le titre de la page d'accueil")
        self.assertIn("Page d'accueil", c["pourquoi"])
        self.assertEqual(c["ou"]["note_id"], self.note)
        self.assertEqual(len(c["comment"]), 3)
        self.assertTrue(all(e["duree_min"] > 0 for e in c["comment"]))
        self.assertEqual(c["fin"], ["Fait", "Pas fait"])
        self.assertIn("Pause", c["apres"])
        texte = orchestrateur.contrat_en_texte(c)
        for champ in ("QUOI", "POURQUOI", "OÙ", "COMMENT", "FIN", "APRÈS"):
            self.assertIn(champ, texte)

    def test_ia_appelee_seulement_sur_evenement(self):
        premier = orchestrateur.tour(JOUR_1, racine=self.racine)
        self.assertEqual(premier["appels_ia"], 1)
        second = orchestrateur.tour(JOUR_1, racine=self.racine)
        self.assertEqual(second["evenements"], 0)
        self.assertEqual(second["appels_ia"], 0)

    def test_agent_propose_rien_n_est_ecrit_avant_validation(self):
        redacteur = agents_mod.charger("redacteur", racine=self.racine, date=JOUR_1)
        pid = voies.proposer(redacteur, "A", "note", "# Slogan\nUn slogan court et clair.",
                             liens=["Page d'accueil"])
        self.assertEqual(len(projets.lister_notes("A", racine=self.racine)), 1)
        orchestrateur.tour(JOUR_1, racine=self.racine)
        p = cc.lire_proposition("A", pid, racine=self.racine)
        self.assertEqual(p["statut"], "en attente")
        self.assertTrue(p["verification"]["ok"], p["verification"])
        self.assertEqual(len(projets.lister_notes("A", racine=self.racine)), 1)
        cc.valider_proposition("A", pid, date=JOUR_1, racine=self.racine)
        self.assertEqual(len(projets.lister_notes("A", racine=self.racine)), 2)

    def test_verification_signale_action_sensible(self):
        redacteur = agents_mod.charger("redacteur", racine=self.racine, date=JOUR_1)
        pid = voies.proposer(redacteur, "A", "tache", "Payer la facture et publier le site",
                             liens=["Inexistante"])
        orchestrateur.tour(JOUR_1, racine=self.racine)
        v = cc.lire_proposition("A", pid, racine=self.racine)["verification"]
        self.assertFalse(v["ok"])
        self.assertTrue(any("action sensible" in p for p in v["problemes"]))
        self.assertTrue(any("inexistantes" in p for p in v["problemes"]))

    def test_agent_limite_a_ses_outils(self):
        verificateur = agents_mod.charger("verificateur", racine=self.racine, date=JOUR_1)
        with self.assertRaises(agents_mod.OutilInterdit):
            verificateur.proposer("A", "note", "je ne devrais pas pouvoir")
        with self.assertRaises(agents_mod.OutilInterdit):
            verificateur.ia("question", "x")
        with self.assertRaises(ValueError):
            agents_mod.Agent("pirate", "proposer", "x", ["supprimer"])

    def test_orchestrateur_voit_toutes_les_taches_et_trie_par_echeance(self):
        projets.creer_tache("B", "Urgent dans B", echeance="2027-01-02", racine=self.racine)
        orchestrateur.tour(JOUR_1, racine=self.racine)
        taches = orchestrateur.taches_a_faire(racine=self.racine)
        self.assertEqual([t["projet"] for t in taches], ["B", "A"])
        self.assertEqual(orchestrateur.prochaine_action(racine=self.racine)["quoi"], "Urgent dans B")

    def test_fait_pas_fait(self):
        orchestrateur.tour(JOUR_1, racine=self.racine)
        self.assertEqual(orchestrateur.terminer("A", self.tache, True, racine=self.racine), "fait")
        self.assertIsNone(orchestrateur.prochaine_action(racine=self.racine))
        t2 = projets.creer_tache("A", "Autre", racine=self.racine)
        orchestrateur.tour(JOUR_1, racine=self.racine)
        self.assertEqual(orchestrateur.terminer("A", t2, False, racine=self.racine), "pas fait")
        # Une tâche « pas faite » reste à faire plus tard.
        self.assertEqual(orchestrateur.prochaine_action(racine=self.racine)["quoi"], "Autre")

    def test_projet_sensible_n_utilise_jamais_une_ia_gratuite(self):
        cc.marquer_projet_sensible("B", racine=self.racine)
        projets.creer_tache("B", "Tâche privée", racine=self.racine)
        orchestrateur.tour(JOUR_1, racine=self.racine)
        contrats = [t["contrat"] for t in orchestrateur.taches_a_faire(racine=self.racine)
                    if t["projet"] == "B"]
        self.assertEqual(contrats[0]["ia"], "demo")
