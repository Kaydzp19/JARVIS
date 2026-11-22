"""
Tests de la marche 7 : cockpit web (serveur local, accès protégé, cerveau 3D).
Le serveur est lancé sur un port libre, avec un dossier de données temporaire.
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
        self.assertEqual(self.appel("/api/etat", jeton="mauvais")[0], 401)
        self.assertEqual(self.appel("/", jeton="")[0], 401)
        code, page = self.appel("/")
        self.assertEqual(code, 200)
        self.assertIn("J.A.R.V.I.S.", page)

    def test_note_avec_lien_fait_apparaitre_un_neurone_relie(self):
        self.json("/api/projet", {"nom": "A"})
        cible = self.json("/api/note", {"projet": "A", "titre": "Budget", "contenu": "300 €"})["id"]
        source = self.json("/api/note", {"projet": "A", "titre": "Plan",
                                         "contenu": "Voir [[Budget]]"})["id"]
        g = self.json("/api/graphe")
        projet = g["projets"][0]
        self.assertEqual({n["titre"] for n in projet["notes"]}, {"Budget", "Plan"})
        self.assertEqual([(l["source"], l["cible"]) for l in projet["liens"]], [(source, cible)])
        # Le graphe ne montre jamais le contenu des notes.
        self.assertNotIn("300", json.dumps(g))
        # Éditeur : liens et rétroliens.
        note = self.json(f"/api/note?projet=A&id={cible}")
        self.assertEqual(note["retroliens"], [{"titre": "Plan", "id": source}])

    def test_demo_complete_dans_le_cockpit(self):
        import demo
        demo.creer_demo(racine=self.racine, bavard=False)
        etat = self.json("/api/etat")
        self.assertEqual({p["nom"] for p in etat["projets"]}, {"Demo-A", "Demo-B"})
        self.assertIsNotNone(etat["maintenant"])
        types = {p["type"] for p in etat["propositions"]}
        self.assertEqual(types, {"note", "synthese", "modification"})
        self.assertEqual(etat["budget"]["depense"], 0)
        self.assertGreater(len(etat["journal"]), 10)

        # Valider la synthèse depuis le cockpit l'écrit dans le cerveau.
        synth = next(p for p in etat["propositions"] if p["type"] == "synthese")
        self.json("/api/proposition", {"projet": synth["projet"], "id": synth["id"],
                                       "action": "valider"})
        g = self.json("/api/graphe")
        titres = {n["titre"] for p in g["projets"] for n in p["notes"]}
        self.assertTrue(any(t.startswith("Synthèse") for t in titres))

        # Fait / Pas fait.
        c = etat["maintenant"]
        self.json("/api/tache", {"projet": c["projet"], "id": c["tache_id"], "fait": True})
        self.assertNotEqual(self.json("/api/etat")["maintenant"]["tache_id"], c["tache_id"])

    def test_erreur_propre(self):
        code, texte = self.appel("/api/note?projet=Inconnu&id=1")
        self.assertEqual(code, 400)
        self.assertIn("erreur", texte)
