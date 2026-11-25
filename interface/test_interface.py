"""
Tests du cockpit (serveur local) : notes, propositions, projets, nuit de démonstration.
Le serveur est lancé sur un port libre, avec un dossier de données temporaire.
(Les pages, la sphère, la conversation et les hologrammes : test_sphere_serveur.py.)
"""

import json
import sys
import threading
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "exemples"))

from interface import serveur_web  # noqa: E402
from noyau.base_tests import TestTemporaire  # noqa: E402

JETON = "jeton-de-test"


class TestCockpit(TestTemporaire):

    def setUp(self):
        super().setUp()
        self.serveur = serveur_web.creer_serveur(port=0, jeton=JETON, racine=self.racine)
        self.base = f"http://127.0.0.1:{self.serveur.server_address[1]}"
        threading.Thread(target=self.serveur.serve_forever, daemon=True).start()

    def tearDown(self):
        self.serveur.shutdown()
        self.serveur.server_close()
        super().tearDown()

    def appel(self, chemin, donnees=None, jeton=JETON):
        corps = None if donnees is None else json.dumps(donnees).encode()
        req = urllib.request.Request(self.base + chemin, data=corps,
                                     headers={"X-Jeton": jeton, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, r.read().decode()
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode()

    def json(self, chemin, donnees=None):
        code, texte = self.appel(chemin, donnees)
        self.assertEqual(code, 200, texte)
        return json.loads(texte)

    def test_acces_protege(self):
        self.assertEqual(self.appel("/api/sphere", jeton="mauvais")[0], 401)
        self.assertEqual(self.appel("/", jeton="")[0], 401)
        self.assertEqual(self.appel("/", jeton=JETON)[0], 200)

    def test_ancien_cockpit_supprime(self):
        for chemin in ("/cockpit", "/api/etat", "/api/cerveau?projet=A", "/api/graphe", "/api/tour",
                       "/api/journal?projet=A", "/api/ia", "/api/reve?projet=A"):
            self.assertEqual(self.appel(chemin)[0], 404, chemin)
        self.assertFalse((Path(serveur_web.__file__).parent / "cockpit.html").exists())

    def test_note_avec_lien_fait_apparaitre_un_neurone_relie(self):
        self.json("/api/projet", {"nom": "A"})
        cible = self.json("/api/note", {"projet": "A", "titre": "Budget", "contenu": "300 €"})["id"]
        source = self.json("/api/note", {"projet": "A", "titre": "Plan",
                                         "contenu": "Voir [[Budget]]"})["id"]
        s = self.json("/api/sphere")
        projet = s["projets"][0]
        self.assertEqual({n["titre"] for n in projet["neurones"]}, {"Budget", "Plan"})
        self.assertEqual([(l["a"], l["b"]) for l in projet["synapses"]], [(source, cible)])
        self.assertNotIn("300", json.dumps(s))           # jamais le contenu des notes
        note = self.json(f"/api/note?projet=A&id={cible}")
        self.assertEqual(note["retroliens"], [{"titre": "Plan", "id": source}])

    def test_valider_une_proposition(self):
        import demo
        demo.creer_demo(racine=self.racine, bavard=False)
        attente = self.json("/api/a_valider")
        synth = next(p for p in attente if p["type"] == "synthese")
        self.json("/api/proposition", {"projet": synth["projet"], "id": synth["id"], "action": "valider"})
        s = self.json("/api/sphere")
        titres = {n["titre"] for p in s["projets"] for n in p["neurones"]}
        self.assertTrue(any(t.startswith("Synthèse") for t in titres))
        self.assertEqual(len(self.json("/api/a_valider")), len(attente) - 1)

    def test_erreur_propre(self):
        code, texte = self.appel("/api/note?projet=Inconnu&id=1")
        self.assertEqual(code, 400)
        self.assertIn("erreur", texte)


class TestNuitDeDemo(TestCockpit):

    def preparer(self, demo=True):
        from noyau import corps_calleux as cc
        from noyau import projets
        projets.creer_projet("Projet A", racine=self.racine)
        if demo:
            cc.marquer_projet_demo("Projet A", racine=self.racine)
        cc.creer_note_humaine("Projet A", "Budget", "Trois cents euros.", racine=self.racine)
        cc.creer_note_humaine("Projet A", "Plan", "Voir [[Budget]].", racine=self.racine)

    def test_simuler_une_nuit(self):
        from noyau import synapses
        self.preparer()
        avant = synapses.lister_synapses("Projet A", racine=self.racine)[0]["poids"]
        r = self.json("/api/nuit", {"projet": "Projet A"})
        self.assertEqual(r["reglages"], {"oubli": 0.02, "apprentissage": 0.10, "seuil_archivage": 0.05})
        apres = synapses.lister_synapses("Projet A", racine=self.racine)[0]["poids"]
        self.assertAlmostEqual(apres, avant * 0.98)
        r2 = self.json("/api/nuit", {"projet": "Projet A"})
        self.assertGreater(r2["nuit"], r["nuit"])

    def test_simuler_une_nuit_interdit_hors_demo(self):
        self.preparer(demo=False)
        code, texte = self.appel("/api/nuit", {"projet": "Projet A"})
        self.assertEqual(code, 400)
        self.assertIn("démonstration", texte)
