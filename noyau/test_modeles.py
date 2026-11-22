"""
Tests de la marche 6, partie C : modèles (local d'abord, cloud payant seulement au réveil).

Un faux serveur Ollama tourne sur la machine pendant les tests : il répond comme
le vrai (adresses /api/tags et /api/generate), sans aucune IA réelle.
"""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from noyau import corps_calleux as cc
from noyau import ia_demo, projets, reve, routeur_ia, sommeil
from noyau.base_tests import JOUR_1, TestTemporaire


def tache_de(demande):
    """Le faux modèle devine la tâche d'après le contenu de la demande."""
    if "combinaisons" in demande:
        return "rever"
    if "contraintes" in demande:
        return "evaluer"
    if "peremption_jours" in demande:
        return "trier"
    if "statistiques" in demande:
        return "resumer"
    return "synthetiser"


class FauxOllama:
    def __init__(self, modeles=("testmodel:latest",)):
        self.prompts, self.options = [], []
        faux = self

        class Gestionnaire(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _json(self, objet):
                corps = json.dumps(objet).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(corps)))
                self.end_headers()
                self.wfile.write(corps)

            def do_GET(self):
                self._json({"models": [{"name": m} for m in modeles]})

            def do_POST(self):
                d = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                faux.prompts.append(d["prompt"])
                faux.options.append(d.get("options", {}))
                demande = json.loads(d["prompt"])
                self._json({"response": ia_demo.repondre(tache_de(demande), d["prompt"])})

        self.serveur = ThreadingHTTPServer(("127.0.0.1", 0), Gestionnaire)
        self.url = f"http://127.0.0.1:{self.serveur.server_address[1]}"
        threading.Thread(target=self.serveur.serve_forever, daemon=True).start()

    def arreter(self):
        self.serveur.shutdown()
        self.serveur.server_close()


class FauxEnLigne(routeur_ia.Fournisseur):
    """Offre en ligne branchée pour le test, qui garde tout ce qu'elle reçoit."""
    branche = True

    def __init__(self, nom, gratuit, payant, cout=0.0):
        self.nom, self.gratuit, self.payant, self.cout = nom, gratuit, payant, cout
        self.recus = []

    def estimer_cout(self, texte):
        return self.cout

    def repondre(self, tache, texte, temperature=None):
        self.recus.append((tache, texte))
        return ia_demo.repondre(tache, texte, temperature)


class BaseModeles(TestTemporaire):

    def setUp(self):
        super().setUp()
        routeur_ia.ModeleLocal._cache.clear()
        projets.creer_projet("A", racine=self.racine)
        n = lambda t, x, **k: cc.creer_note_humaine("A", t, x, date=JOUR_1, racine=self.racine, **k)
        n("Recettes", "Cuisiner simple le dimanche.")
        n("Clients", "Trouver des clients du quartier.")
        n("Course", "Courir trois fois par semaine.")
        n("Lecture", "Lire un livre par mois.")
        n("Coffre", "Combinaison secrète 7777.", sensible=True)
        n("Banque", "Relevé privé 8888.", sensible=True)
        self.gemini = FauxEnLigne("gemini", gratuit=True, payant=False)
        self.claude = FauxEnLigne("claude", gratuit=False, payant=True, cout=0.01)
        self.ollama = None

    def tearDown(self):
        if self.ollama:
            self.ollama.arreter()
        super().tearDown()

    def reglages(self, texte):
        (self.racine / "reglages.local").write_text(texte, encoding="utf-8")

    def avec_ollama(self):
        self.ollama = FauxOllama()
        self.reglages(f"modele_local=testmodel\nollama_url={self.ollama.url}\n")

    def dormir(self, fournisseurs):
        return sommeil.dormir(JOUR_1, projet="A", racine=self.racine, fournisseurs=fournisseurs)

    def tout(self, fournisseur):
        return " ".join(t for _, t in fournisseur.recus)


class TestModeleLocal(BaseModeles):

    def test_aucun_modele_local_par_defaut(self):
        self.assertFalse(routeur_ia.ModeleLocal().disponible())

    def test_modele_local_configure_mais_ollama_eteint(self):
        self.reglages("modele_local=testmodel\nollama_url=http://127.0.0.1:9\n")
        self.assertFalse(routeur_ia.ModeleLocal().disponible())

    def test_modele_absent_d_ollama(self):
        self.ollama = FauxOllama(modeles=("autre:latest",))
        self.reglages(f"modele_local=testmodel\nollama_url={self.ollama.url}\n")
        self.assertFalse(routeur_ia.ModeleLocal().disponible())

    def test_le_routeur_prefere_le_local(self):
        self.avec_ollama()
        local = routeur_ia.ModeleLocal()
        self.assertTrue(local.disponible())
        f = routeur_ia.choisir("courante", False, {"local": local, "gemini": self.gemini,
                                                   "demo": routeur_ia.IADemo()})
        self.assertEqual(f.nom, "local")

    def test_avec_modele_local_tout_reste_sur_la_machine(self):
        self.avec_ollama()
        bilan = self.dormir({"local": routeur_ia.ModeleLocal(), "gemini": self.gemini,
                             "demo": routeur_ia.IADemo()})
        self.assertEqual(self.gemini.recus, [])
        tout_local = " ".join(self.ollama.prompts)
        self.assertIn("7777", tout_local)  # les notes sensibles peuvent entrer… en local
        self.assertEqual(bilan["appels_ia"], len(self.ollama.prompts))
        r = reve.lister("A", racine=self.racine)[0]
        self.assertEqual(r["details"]["ia"], "local")
        self.assertIn(1.0, [o.get("temperature") for o in self.ollama.options])  # rêve créatif


class TestSansModeleLocal(BaseModeles):

    def test_sensibles_exclues_et_offre_gratuite_permise(self):
        bilan = self.dormir({"gemini": self.gemini, "demo": routeur_ia.IADemo()})
        taches = [t for t, _ in self.gemini.recus]
        self.assertIn("rever", taches)        # le non-sensible passe par l'offre gratuite
        texte = self.tout(self.gemini)
        for interdit in ("7777", "8888", "Coffre", "Banque"):
            self.assertNotIn(interdit, texte)
        self.assertIsNotNone(bilan["projets"]["A"]["reve"])

    def test_projet_sensible_ne_reve_pas_sans_local(self):
        cc.marquer_projet_sensible("A", racine=self.racine)
        self.dormir({"gemini": self.gemini, "demo": routeur_ia.IADemo()})
        self.assertEqual(self.gemini.recus, [])
        self.assertEqual(reve.lister("A", racine=self.racine), [])

    def test_projet_sensible_reve_avec_local(self):
        cc.marquer_projet_sensible("A", racine=self.racine)
        self.avec_ollama()
        self.dormir({"local": routeur_ia.ModeleLocal(), "gemini": self.gemini,
                     "demo": routeur_ia.IADemo()})
        self.assertEqual(self.gemini.recus, [])
        self.assertEqual(len(reve.lister("A", racine=self.racine)), 1)


class TestCloudPourReveil(BaseModeles):

    def ia(self):
        return {"gemini": self.gemini, "claude": self.claude, "demo": routeur_ia.IADemo()}

    def test_cloud_interdit_par_defaut(self):
        self.dormir(self.ia())
        self.assertEqual(self.claude.recus, [])

    def test_cloud_autorise_seulement_pour_le_reveil(self):
        self.reglages("cloud_pour_reveil=true\n")
        bilan = self.dormir(self.ia())
        self.assertEqual([t for t, _ in self.claude.recus], ["evaluer"])
        self.assertAlmostEqual(bilan["cout"], 0.01)
        self.assertAlmostEqual(routeur_ia.depense_du_mois(JOUR_1, self.racine), 0.01)
        self.assertEqual(reve.lister("A", racine=self.racine)[0]["details"]["ia"], "claude")
        texte = self.tout(self.claude)
        for interdit in ("7777", "8888", "Coffre", "Banque"):
            self.assertNotIn(interdit, texte)

    def test_cloud_soumis_au_budget_mensuel_du_routeur(self):
        self.reglages("cloud_pour_reveil=true\nBUDGET_IA_MAX_EUR_MOIS=0.005\n")
        bilan = self.dormir(self.ia())
        self.assertIn("Plafond IA atteint", bilan["arret"])
        self.assertEqual(self.claude.recus, [])

    def test_jamais_de_cloud_pour_une_idee_sensible(self):
        cc.marquer_projet_sensible("A", racine=self.racine)
        self.ollama = FauxOllama()
        self.reglages(f"modele_local=testmodel\nollama_url={self.ollama.url}\n"
                      "cloud_pour_reveil=true\n")
        self.dormir(dict(self.ia(), local=routeur_ia.ModeleLocal()))
        self.assertEqual(self.claude.recus, [])
        self.assertEqual(self.gemini.recus, [])

    def test_idees_par_projet(self):
        self.reglages("idees_par_projet=2\ncandidates_par_nuit=4\n")
        bilan = self.dormir({"demo": routeur_ia.IADemo()})
        self.assertEqual(len(bilan["projets"]["A"]["reves"]), 2)
        self.assertEqual(reve.lister("A", racine=self.racine)[0]["details"]["idees_evaluees"], 4)
