"""
Tests de la marche 7 · design : le serveur de l'interface « sphère ».

- les pages (/ = le cockpit, /sphere/… = ses fichiers) sont protégées ;
- /api/sphere ne contient que des titres, des identifiants et des poids ;
- /api/demander : routage par code, trace sans texte de note, renforcement des notes validées ;
- /api/affichage/action : mise à jour en lecture, garde d'écriture ;
- fournisseurs : machine (jamais de sudo, jamais d'arguments de processus), dépenses, nuit.
"""

import json
import sys
import threading
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "exemples"))

import demo  # noqa: E402
from interface import conversation, fournisseurs, serveur_web  # noqa: E402
from noyau import affichage, projets  # noqa: E402
from noyau import corps_calleux as cc  # noqa: E402
from noyau.base_tests import TestTemporaire  # noqa: E402

JETON = "jeton-de-test"
RACINE_DEPOT = Path(__file__).resolve().parent.parent


class Base(TestTemporaire):

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
                return r.status, r.read().decode(), r.headers.get("Content-Type", "")
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode(), e.headers.get("Content-Type", "")

    def json(self, chemin, donnees=None, code=200):
        c, texte, _ = self.appel(chemin, donnees)
        self.assertEqual(c, code, texte)
        return json.loads(texte)


class TestPages(Base):

    def test_pages_protegees(self):
        for chemin in ("/", "/sphere/js/main.js", "/api/sphere", "/api/systeme"):
            self.assertEqual(self.appel(chemin, jeton="")[0], 401, chemin)

    def test_page_sphere(self):
        code, page, type_ = self.appel("/")
        self.assertEqual(code, 200)
        self.assertIn("text/html", type_)
        for attendu in ("J.A.R.V.I.S", "Second cerveau", "#010409", "three@0.160.0", "js/main.js",
                        "Démo · données fictives", 'id="a-valider"', 'id="journal"', "VOIX"):
            self.assertIn(attendu, page)
        # Identité visuelle : palette et polices (feuille de style).
        css = self.appel("/sphere/css/jarvis.css")[1]
        for attendu in ("#010409", "#4CC9FF", "#FF8A3D", "#FFD84A", "#F1F8FF", "#8FA9C2",
                        "Rajdhani", "JetBrains Mono", "prefers-reduced-motion", "max-width:900px"):
            self.assertIn(attendu, css)
        self.assertIn("catalogue-liste", self.appel("/sphere/catalogue.html")[1])

    def test_fichiers_statiques(self):
        code, texte, type_ = self.appel("/sphere/js/main.js")
        self.assertEqual(code, 200)
        self.assertIn("javascript", type_)
        self.assertEqual(self.appel("/sphere/css/jarvis.css")[2], "text/css; charset=utf-8")
        # On ne sort jamais du dossier de l'interface, et les tests ne sont pas servis.
        for chemin in ("/sphere/../serveur_web.py", "/sphere/%2e%2e/serveur_web.py",
                       "/sphere/../../LISEZ-MOI.md", "/sphere/inexistant.js",
                       "/sphere/tests/contrat.test.mjs"):
            self.assertEqual(self.appel(chemin)[0], 404, chemin)


class TestApi(Base):

    def setUp(self):
        super().setUp()
        demo.creer_demo(racine=self.racine, bavard=False)

    def test_sphere_sans_contenu(self):
        d = self.json("/api/sphere")
        self.assertEqual([p["nom"] for p in d["projets"]], ["Projet A", "Projet B"])
        self.assertTrue(d["demo"])
        a = d["projets"][0]
        self.assertGreaterEqual(len(a["neurones"]), 10)
        self.assertTrue(a["synapses"])
        self.assertEqual(set(a["neurones"][0]), {"id", "titre", "validee", "sensible", "liens"})
        brut = json.dumps(d, ensure_ascii=False)
        for interdit in ("contenu", "extrait"):
            self.assertNotIn(interdit, brut)
        for n in projets.lister_notes("Projet A", self.racine):
            texte = projets.lire_note("Projet A", n["id"], self.racine)
            for ligne in texte.splitlines():
                if len(ligne) > 30 and not ligne.startswith("#"):
                    self.assertNotIn(ligne, brut)
        self.assertEqual(d["compteurs"]["neurones"], sum(len(p["neurones"]) for p in d["projets"]))

    def test_demander_se_souvenir(self):
        r = self.json("/api/demander", {"texte": "Que sais-tu des clients ?", "projet": "Projet A"})
        self.assertEqual(r["route"], "se_souvenir")
        self.assertTrue(r["outil"].startswith('se_souvenir(projet="Projet A", requête="'))
        self.assertEqual(r["routeur"], "routeur : aucun appel IA")
        trace = r["recherche"]["traces"][0]
        self.assertFalse(trace["appel_ia"])
        self.assertLessEqual(len(trace["retenues"]), 6)
        self.assertEqual(r["affichage"]["scene"], "notes_retenues")
        brut = json.dumps(r, ensure_ascii=False)
        self.assertNotIn("extrait", brut)
        self.assertNotIn('"contenu"', brut)
        self.assertIsNotNone(r["renforcement"])

    def test_demander_tous_les_projets_en_lecture_seule(self):
        avant = len(projets.lire_journal("Projet A", self.racine))
        r = self.json("/api/demander", {"texte": "Où en sont mes projets ?", "projet": "*"})
        self.assertEqual(len(r["recherche"]["traces"]), 2)
        for t in r["recherche"]["traces"]:
            self.assertLessEqual(len(t["retenues"]), 4)
        self.assertIsNone(r["renforcement"])
        self.assertEqual(len(projets.lire_journal("Projet A", self.racine)), avant)
        self.assertEqual(r["affichage"]["projet"], "*")

    def test_demander_hologrammes(self):
        for texte, scene in (("État de ma machine", "machine"), ("Résumé de la nuit", "resume_nuit"),
                             ("Graphique de mes dépenses", "graphique"), ("Météo", "meteo")):
            r = self.json("/api/demander", {"texte": texte, "projet": "Projet A"})
            self.assertEqual(r["affichage"]["scene"], scene, texte)
            self.assertEqual(r["routeur"], "routeur : aucun appel IA")
            self.assertEqual(affichage.valider(r["affichage"]), [])
        self.assertFalse(r["affichage"]["donnees"]["disponible"])   # position non réglée

    def test_demander_message_vide(self):
        self.assertIn("erreur", self.json("/api/demander", {"texte": " ", "projet": "Projet A"}, 400))

    def test_note_sensible_refusee(self):
        cc.creer_note_humaine("Projet A", "Coffre", "code 1234 du coffre", sensible=True,
                              racine=self.racine)
        r = self.json("/api/demander", {"texte": "Ouvre la note Coffre", "projet": "Projet A"})
        self.assertEqual(r["affichage"]["scene"], "note_privee")
        self.assertEqual(r["affichage"]["donnees"]["caracteres"], len("code 1234 du coffre"))
        self.assertNotIn("1234", json.dumps(r))
        r = self.json("/api/demander", {"texte": "Ouvre la note Offre", "projet": "Projet A"})
        self.assertIsNone(r["affichage"])
        self.assertEqual(r.get("ouvrir_note", {}).get("projet"), "Projet A")

    def test_action_periode_met_a_jour(self):
        r = self.json("/api/demander", {"texte": "Mes dépenses IA", "projet": "Projet A"})
        ev = r["affichage"]
        self.assertEqual(len(ev["donnees"]["serie"]), 6)
        res = self.json("/api/affichage/action", {"widget": ev["id"], "action": "periode",
                                                  "params": {"periode": "7 j"}})
        self.assertEqual(res["type"], "mise_a_jour")
        self.assertEqual(res["affichage"]["id"], ev["id"])
        self.assertEqual(res["affichage"]["version"], 2)
        self.assertEqual(len(res["affichage"]["donnees"]["serie"]), 7)
        liste = self.json(f"/api/affichage?apres={ev['id'] - 1}")
        self.assertEqual(liste[0]["version"], 2)

    def test_action_ecriture_devient_proposition(self):
        ev = affichage.afficher("liste", "Tâches", {}, projet="Projet A",
                                actions=[{"id": "supprimer", "libelle": "Supprimer"}],
                                racine=self.racine)
        avant = len(self.json("/api/a_valider"))
        res = self.json("/api/affichage/action", {"widget": ev["id"], "action": "supprimer",
                                                  "params": {}})
        self.assertEqual(res["type"], "a_valider")
        self.assertEqual(len(self.json("/api/a_valider")), avant + 1)

    def test_widgets_permanents(self):
        m = self.json("/api/systeme")
        self.assertIn("cpu", m)
        self.assertIsNone(m["temperature"])
        d = self.json("/api/depenses")
        self.assertEqual(set(d) >= {"session", "aujourd_hui", "mois", "plafond", "serie"}, True)
        j = self.json("/api/journal_du_jour")
        self.assertIsInstance(j, list)


class TestFournisseurs(TestTemporaire):

    def test_machine_sans_sudo_ni_arguments(self):
        source = (RACINE_DEPOT / "interface" / "fournisseurs.py").read_text(encoding="utf-8")
        self.assertNotIn('"sudo"', source)
        self.assertNotIn("args=", source)
        m = fournisseurs.machine()
        for p in m["processus"]:
            self.assertNotIn(" ", p["nom"].strip()[:1])
        self.assertLessEqual(len(m["historique"]), 24)

    def test_journal_du_jour_masque_les_projets_sensibles(self):
        projets.creer_projet("Privé", racine=self.racine)
        cc.marquer_projet_sensible("Privé", racine=self.racine)
        cc.journal("Privé", "rendez-vous chez le médecin", racine=self.racine)
        from datetime import date
        lignes = fournisseurs.journal_du_jour(self.racine, aujourd_hui=date.today())
        self.assertTrue(lignes)
        self.assertNotIn("médecin", json.dumps(lignes, ensure_ascii=False))
        self.assertTrue(all(l["prive"] for l in lignes if l["projet"] == "Privé"))

    def test_nuit_lit_le_bilan(self):
        demo.creer_demo(racine=self.racine, bavard=False)
        n = fournisseurs.nuit("Projet A", self.racine)
        self.assertIsNotNone(n["date"])
        self.assertGreaterEqual(n["propositions_en_attente"], 1)

    def test_meteo_sans_reseau(self):
        import os
        os.environ["METEO_LATITUDE"], os.environ["METEO_LONGITUDE"] = "48.85", "2.35"

        def ouvrir_en_panne(*a, **k):
            raise OSError("pas de réseau")
        self.assertFalse(fournisseurs.meteo(ouvrir_en_panne)["disponible"])

    def test_routeur_par_code(self):
        self.assertEqual(conversation.router("cpu de la machine ?"), "machine")
        self.assertEqual(conversation.router("Va-t-il pleuvoir ?"), "meteo")
        self.assertEqual(conversation.router("ouvre la note Budget"), "ouvrir_note")
        self.assertEqual(conversation.router("que sais-tu du lancement ?"), "se_souvenir")
