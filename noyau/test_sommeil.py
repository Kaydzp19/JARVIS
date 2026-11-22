"""
Tests de la marche 6 : sommeil (oubli + synthèse nocturne).
"""

from datetime import timedelta

from noyau import corps_calleux as cc
from noyau import projets, sommeil, synapses
from noyau.base_tests import JOUR_1, TestTemporaire


class TestSommeil(TestTemporaire):

    def setUp(self):
        super().setUp()
        projets.creer_projet("A", racine=self.racine)
        # Trois notes reliées en triangle, écrites (donc validées) par Kayd.
        self.a = cc.creer_note_humaine("A", "Clients", "Qui achète. Voir [[Prix]].",
                                       date=JOUR_1, racine=self.racine)
        self.b = cc.creer_note_humaine("A", "Prix", "Combien. Voir [[Offre]].",
                                       date=JOUR_1, racine=self.racine)
        self.c = cc.creer_note_humaine("A", "Offre", "Quoi. Voir [[Clients]].",
                                       date=JOUR_1, racine=self.racine)
        cc.modifier_note_humaine("A", self.a, "Qui achète. Voir [[Prix]] et [[Offre]].",
                                 date=JOUR_1, racine=self.racine)
        self.seule = cc.creer_note_humaine("A", "Divers", "Sans lien. Voir [[Clients]].",
                                           date=JOUR_1, racine=self.racine)

    def utiliser_pendant(self, jours):
        for i in range(jours):
            cc.activer("A", [self.a, self.b, self.c], date=JOUR_1 + timedelta(days=i),
                       racine=self.racine)

    def test_au_reveil_une_synthese_est_proposee_avec_sa_raison(self):
        self.utiliser_pendant(3)
        reveil = JOUR_1 + timedelta(days=3)
        bilan = sommeil.dormir(reveil, racine=self.racine)
        self.assertEqual(len(bilan["projets"]["A"]["syntheses_proposees"]), 1)
        p = cc.lister_propositions("A", "en attente", racine=self.racine)[0]
        self.assertEqual(p["type"], "synthese")
        self.assertEqual(set(p["liens"]), {"Clients", "Prix", "Offre"})
        self.assertNotIn("Divers", p["liens"])
        self.assertIn("très liées", p["raison"])
        journal = projets.lire_journal("A", racine=self.racine)
        self.assertTrue(any(l["acteur"] == "sommeil" and "1 synthèse" in l["raison"]
                            for l in journal))
        # Rien n'est écrit dans les notes avant la validation.
        self.assertEqual(len(projets.lister_notes("A", racine=self.racine)), 4)

    def test_pas_de_doublon_la_nuit_suivante(self):
        self.utiliser_pendant(3)
        sommeil.dormir(JOUR_1 + timedelta(days=3), racine=self.racine)
        bilan = sommeil.dormir(JOUR_1 + timedelta(days=4), racine=self.racine)
        self.assertEqual(bilan["projets"]["A"]["syntheses_proposees"], [])

    def test_sans_usage_pas_de_synthese_et_oubli_applique(self):
        bilan = sommeil.dormir(JOUR_1 + timedelta(days=3), racine=self.racine)
        self.assertEqual(bilan["projets"]["A"]["syntheses_proposees"], [])
        for s in synapses.lister_synapses("A", racine=self.racine):
            self.assertLess(s["poids"], 0.1)

    def test_la_synthese_validee_rejoint_le_cerveau(self):
        self.utiliser_pendant(3)
        sommeil.dormir(JOUR_1 + timedelta(days=3), racine=self.racine)
        pid = cc.lister_propositions("A", "en attente", racine=self.racine)[0]["id"]
        nid = cc.valider_proposition("A", pid, date=JOUR_1 + timedelta(days=3), racine=self.racine)
        cibles = {s["note_cible"] for s in synapses.lister_synapses("A", racine=self.racine)
                  if s["note_source"] == nid}
        self.assertEqual(cibles, {self.a, self.b, self.c})

    def test_fichier_launchd(self):
        texte = sommeil.plist_launchd("/Users/kayd/JARVIS", "/Users/kayd/.jarvis",
                                      python="/usr/bin/python3")
        self.assertIn("<string>/Users/kayd/JARVIS/jarvis.py</string>", texte)
        self.assertIn("<string>dormir</string>", texte)
        self.assertIn("<key>RunAtLoad</key>", texte)        # ouverture de session
        self.assertIn("<key>StartInterval</key>", texte)    # relancé au réveil du Mac
        self.assertIn("<integer>600</integer>", texte)
        self.assertNotIn("pmset", texte)                    # on ne touche pas à la veille


class TestCommandeDormir(TestTemporaire):

    def setUp(self):
        super().setUp()
        for p in ("A", "B"):
            projets.creer_projet(p, racine=self.racine)
            cc.creer_note_humaine(p, "Note", "Une note.", date=JOUR_1, racine=self.racine)

    def test_un_seul_projet(self):
        bilan = sommeil.dormir(JOUR_1, projet="A", racine=self.racine)
        self.assertEqual(list(bilan["projets"]), ["A"])
        self.assertIsNotNone(sommeil.dernier_sommeil("A", self.racine))
        self.assertIsNone(sommeil.dernier_sommeil("B", self.racine))
        with self.assertRaises(KeyError):
            sommeil.dormir(JOUR_1, projet="Inconnu", racine=self.racine)

    def test_regle_des_24_heures(self):
        from datetime import datetime
        t0 = datetime(2027, 1, 1, 8, 0)
        self.assertEqual(sorted(sommeil.dormir(t0, racine=self.racine)["projets"]), ["A", "B"])
        # Réveils suivants du Mac dans les 24 h : rien.
        for heures in (1, 12, 23.9):
            bilan = sommeil.dormir(t0 + timedelta(hours=heures), racine=self.racine)
            self.assertEqual(bilan["projets"], {}, heures)
            self.assertEqual(sorted(bilan["ignores"]), ["A", "B"])
            self.assertEqual(bilan["appels_ia"], 0)
        # 24 h après : on rêve à nouveau.
        bilan = sommeil.dormir(t0 + timedelta(hours=24), racine=self.racine)
        self.assertEqual(sorted(bilan["projets"]), ["A", "B"])

    def test_regle_des_24_heures_par_projet(self):
        from datetime import datetime
        t0 = datetime(2027, 1, 1, 8, 0)
        sommeil.dormir(t0, projet="A", racine=self.racine)
        bilan = sommeil.dormir(t0 + timedelta(hours=2), racine=self.racine)
        self.assertEqual(list(bilan["projets"]), ["B"])
        self.assertEqual(bilan["ignores"], ["A"])

    def test_commande_autonome(self):
        import os
        import subprocess
        import sys
        from pathlib import Path
        jarvis = Path(__file__).resolve().parent.parent / "jarvis.py"
        lancer = lambda *a: subprocess.run([sys.executable, str(jarvis), "dormir", *a],
                                           capture_output=True, text=True, env=dict(os.environ),
                                           timeout=60)
        r = lancer("A", "--date", "2027-01-01T08:00")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('"A"', r.stdout)
        r = lancer("--silencieux", "--date", "2027-01-01T09:00")  # comme le Mac, 1 h après
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('"B"', r.stdout)         # B n'avait pas encore rêvé
        r = lancer("--silencieux", "--date", "2027-01-01T10:00")
        self.assertEqual(r.stdout.strip(), "")  # rien à faire : rien d'affiché

    def test_chaque_phase_ecrit_au_journal(self):
        sommeil.dormir(JOUR_1, projet="A", racine=self.racine)
        evenements = [l["evenement"] for l in projets.lire_journal("A", racine=self.racine)
                      if l["acteur"] == "sommeil"]
        for nom, _ in sommeil.PHASES:
            self.assertTrue(any(e.startswith(f"sommeil · {nom}") for e in evenements),
                            f"pas de ligne de journal pour la phase {nom}")
        self.assertEqual(evenements[-1], "sommeil terminé")

    def test_lire_json_tolerant(self):
        self.assertEqual(sommeil.lire_json('Voici : {"a": 1} merci'), {"a": 1})
        self.assertIsNone(sommeil.lire_json("pas de JSON"))
