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
