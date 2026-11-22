"""
Tests de la marche 6, partie 2 : phase de tri (code puis IA légère).
"""

from noyau import corps_calleux as cc
from noyau import projets, routeur_ia, sommeil
from noyau.base_tests import JOUR_1, TestTemporaire


class Espion(routeur_ia.IADemo):
    """IA de démonstration qui garde une copie de tout ce qu'on lui envoie."""

    def __init__(self, cout_par_appel=0.0):
        super().__init__(cout_par_appel)
        self.recus = []

    def repondre(self, tache, texte, temperature=None):
        self.recus.append((tache, texte, temperature))
        return super().repondre(tache, texte, temperature)


class TestTri(TestTemporaire):

    def setUp(self):
        super().setUp()
        projets.creer_projet("A", racine=self.racine)
        self.espion = Espion()
        self.ia = {"demo": self.espion}

    def note(self, titre, texte, **k):
        return cc.creer_note_humaine("A", titre, texte, date=JOUR_1, racine=self.racine, **k)

    def dormir(self, jours=0):
        from datetime import timedelta
        return sommeil.dormir(JOUR_1 + timedelta(days=jours), projet="A", racine=self.racine,
                              fournisseurs=self.ia)

    def propositions(self):
        return [p for p in cc.lister_propositions("A", racine=self.racine)
                if p["type"] == "modification"]

    def test_doublon_devient_une_proposition_jamais_une_ecriture(self):
        a = self.note("Prix", "Le prix de base est de 490 euros par page. Voir [[Offre]].")
        self.note("Offre", "Une page. Voir [[Prix]].")
        b = self.note("Tarifs", "Le prix de base est de 490 euros par page.")
        avant = projets.lire_note("A", b, racine=self.racine)
        bilan = self.dormir()
        p = next(p for p in self.propositions() if p["raison"].startswith("tri:doublon"))
        self.assertEqual(p["note_cible"], b)
        self.assertIn("[[Prix]]", p["contenu"])
        self.assertIn(p["id"], bilan["projets"]["A"]["tri_propositions"])
        # Rien n'est écrit tant que Kayd n'a pas validé.
        self.assertEqual(projets.lire_note("A", b, racine=self.racine), avant)
        cc.valider_proposition("A", p["id"], date=JOUR_1, racine=self.racine)
        self.assertIn("Doublon probable", projets.lire_note("A", b, racine=self.racine))
        self.assertEqual(len(projets.lister_notes("A", racine=self.racine)), 3)  # rien supprimé
        self.assertNotEqual(a, b)

    def test_orpheline_et_suggestion_de_lien(self):
        self.note("Prix", "Prix de la page. Voir [[Offre]].")
        self.note("Offre", "Offre d'une page. Voir [[Prix]].")
        seule = self.note("Idée prix réduit", "Un prix réduit pour les associations.")
        self.dormir()
        p = next(p for p in self.propositions() if p["note_cible"] == seule)
        self.assertTrue(p["raison"].startswith("tri:orpheline"))
        self.assertIn("[[Prix]]", p["contenu"])

    def test_perimee(self):
        self.note("Récent", "Texte récent. Voir [[Vieux]].")
        vieux = projets.creer_note("A", "Vieux", "Ancien texte. Voir [[Récent]].",
                                   racine=self.racine, validee=True,
                                   horodatage="2026-01-01T10:00:00")
        from noyau import synapses
        synapses.relier_note("A", vieux, JOUR_1, racine=self.racine)
        self.dormir()
        p = next(p for p in self.propositions() if p["note_cible"] == vieux)
        self.assertTrue(p["raison"].startswith("tri:perimee"))
        self.assertIn("À revoir", p["contenu"])

    def test_pas_de_repetition_meme_apres_refus(self):
        self.note("Seule", "Une note sans aucun lien.")
        self.dormir()
        p = self.propositions()[0]
        cc.refuser_proposition("A", p["id"], racine=self.racine)
        bilan = self.dormir(1)
        self.assertEqual(bilan["projets"]["A"]["tri_propositions"], [])

    def test_au_plus_trois_propositions_par_nuit(self):
        for i in range(6):
            self.note(f"Isolée {i}", f"Sujet numéro {i} sans lien {'x' * i}.")
        bilan = self.dormir()
        self.assertEqual(len(bilan["projets"]["A"]["tri_propositions"]), 3)

    def test_notes_sensibles_jamais_envoyees(self):
        self.note("Publique", "Texte public sans rien de privé.")
        self.note("Secret", "Code du coffre 1234.", sensible=True)
        self.dormir()
        envoye = " ".join(t for _, t, _ in self.espion.recus)
        self.assertNotIn("coffre", envoye)
        self.assertNotIn("Secret", envoye)
        self.assertIn("Publique", envoye)

    def test_projet_sensible_aucune_note_envoyee(self):
        cc.marquer_projet_sensible("A", racine=self.racine)
        self.note("Privé", "Rien ne doit sortir.")
        self.dormir()
        self.assertFalse(any("Privé" in t for _, t, _ in self.espion.recus))

    def test_modification_doit_viser_une_note(self):
        with self.assertRaises(ValueError):
            cc.proposer("A", "modification", "nouveau texte", racine=self.racine)
        with self.assertRaises(ValueError):
            cc.proposer("A", "modification", "nouveau texte", note_cible=99, racine=self.racine)
