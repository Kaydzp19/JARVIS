"""
Tests de la brique 4 (hémisphère actif) : chaque voie produit une proposition,
seulement sur événement, sans jamais écrire.
"""

from datetime import timedelta

from noyau import corps_calleux as cc
from noyau import orchestrateur, projets, reve, sommeil
from noyau.base_tests import JOUR_1, TestTemporaire


class TestVoies(TestTemporaire):

    def setUp(self):
        super().setUp()
        projets.creer_projet("A", racine=self.racine)

    def note(self, titre, texte, **k):
        return cc.creer_note_humaine("A", titre, texte, date=JOUR_1, racine=self.racine, **k)

    def props(self, prefixe):
        return [p for p in cc.lister_propositions("A", racine=self.racine)
                if (p["raison"] or "").startswith(prefixe)]

    def test_planifier_propose_une_tache_quand_il_n_y_en_a_plus(self):
        self.note("Objectif", "Lancer le site en mars.")
        orchestrateur.tour(JOUR_1, racine=self.racine)
        p = self.props("voie:planifier")
        self.assertEqual(len(p), 1)
        self.assertEqual((p[0]["type"], p[0]["acteur"]), ("tache", "agent:planificateur"))
        self.assertEqual(p[0]["liens"], ["Objectif"])
        self.assertEqual(projets.lister_taches("A", racine=self.racine), [])  # rien d'écrit
        orchestrateur.tour(JOUR_1, racine=self.racine)
        self.assertEqual(len(self.props("voie:planifier")), 1)  # pas de doublon
        # Validée par Kayd, elle devient une vraie tâche, que l'orchestrateur planifie.
        cc.valider_proposition("A", p[0]["id"], racine=self.racine)
        orchestrateur.tour(JOUR_1, racine=self.racine)
        self.assertEqual(orchestrateur.prochaine_action(racine=self.racine)["ou"]["titre"],
                         "Objectif")

    def test_verifier_signale_un_lien_casse(self):
        nid = self.note("Plan", "Voir [[Fantôme]] pour la suite.")
        avant = projets.lire_note("A", nid, racine=self.racine)
        orchestrateur.tour(JOUR_1, racine=self.racine)
        p = self.props("voie:verifier:lien")
        self.assertEqual(len(p), 1)
        self.assertEqual((p[0]["type"], p[0]["note_cible"]), ("modification", nid))
        self.assertIn("Lien cassé", p[0]["contenu"])
        self.assertEqual(projets.lire_note("A", nid, racine=self.racine), avant)
        cc.valider_proposition("A", p[0]["id"], racine=self.racine)
        self.assertIn("Lien cassé", projets.lire_note("A", nid, racine=self.racine))
        orchestrateur.tour(JOUR_1, racine=self.racine)
        self.assertEqual(len(self.props("voie:verifier:lien")), 1)

    def test_comparer_deux_notes_tres_proches(self):
        self.note("Prix", "Le prix de base est de 490 euros par page.")
        self.note("Tarifs", "Le prix de base est de 490 euros la page.")
        bilan = orchestrateur.tour(JOUR_1, racine=self.racine)
        p = self.props("voie:comparer")
        self.assertEqual(len(p), 1)
        self.assertEqual(set(p[0]["liens"]), {"Prix", "Tarifs"})
        self.assertEqual(p[0]["acteur"], "agent:comparateur")
        self.assertGreaterEqual(bilan["appels_ia"], 1)  # la comparaison passe par le routeur
        orchestrateur.tour(JOUR_1, racine=self.racine)
        self.assertEqual(len(self.props("voie:comparer")), 1)

    def test_proposer_depuis_une_idee_revee_gardee(self):
        for t in ("Recettes", "Clients", "Course", "Lecture"):
            self.note(t, f"Une note sur {t.lower()} sans lien.")
        projets.creer_tache("A", "Une tâche", racine=self.racine)
        sommeil.dormir(JOUR_1, projet="A", racine=self.racine)
        r = reve.lister("A", racine=self.racine)[0]
        reve.garder("A", r["id"], "bonne idée", racine=self.racine)
        orchestrateur.tour(JOUR_1 + timedelta(days=1), racine=self.racine)
        p = self.props(f"voie:proposer:reve:{r['id']}")
        self.assertEqual(len(p), 1)
        self.assertEqual(p[0]["acteur"], "agent:redacteur")
        self.assertEqual(p[0]["liens"], r["sources_titres"])

    def test_ia_seulement_sur_evenement(self):
        self.note("Seule", "Rien à comparer.")
        projets.creer_tache("A", "Tâche", racine=self.racine)
        orchestrateur.tour(JOUR_1, racine=self.racine)       # planifie la tâche (1 appel IA)
        bilan = orchestrateur.tour(JOUR_1, racine=self.racine)
        self.assertEqual((bilan["evenements"], bilan["appels_ia"]), (0, 0))
