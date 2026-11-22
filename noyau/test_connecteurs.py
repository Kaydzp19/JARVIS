"""
Tests du routeur IA : mode SIMULÉ par défaut, vrais branchements Gemini et Claude.

Les « vrais » services sont remplacés par un faux serveur local qui répond
comme eux. Aucune vraie clé n'est utilisée : « cle-de-test » n'ouvre rien.
"""

import json
import threading
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from noyau import corps_calleux as cc
from noyau import projets, routeur_ia, sommeil
from noyau.base_tests import JOUR_1, TestTemporaire


class FauxService:
    """Faux Gemini + faux Claude sur le même port. Garde chaque requête reçue."""

    def __init__(self, refus=False):
        self.requetes = []
        faux = self

        class G(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_POST(self):
                corps = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                faux.requetes.append({"chemin": self.path,
                                      "entetes": {k.lower(): v for k, v in self.headers.items()},
                                      "corps": corps})
                if self.path.startswith("/v1beta/models/"):
                    rep = {"candidates": [{"content": {"parts": [{"text": '{"ok": "gemini"}'}]}}]}
                elif refus:
                    rep = {"content": [], "stop_reason": "refusal"}
                else:
                    rep = {"content": [{"type": "thinking", "thinking": ""},
                                       {"type": "text", "text": "réponse de Claude"}],
                           "stop_reason": "end_turn",
                           "usage": {"input_tokens": 1000, "output_tokens": 500}}
                donnees = json.dumps(rep).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(donnees)))
                self.end_headers()
                self.wfile.write(donnees)

        self.serveur = ThreadingHTTPServer(("127.0.0.1", 0), G)
        self.url = f"http://127.0.0.1:{self.serveur.server_address[1]}"
        threading.Thread(target=self.serveur.serve_forever, daemon=True).start()

    def arreter(self):
        self.serveur.shutdown()
        self.serveur.server_close()


class BaseConnecteurs(TestTemporaire):

    def setUp(self):
        super().setUp()
        routeur_ia.ModeleLocal._cache.clear()
        self.faux = None

    def tearDown(self):
        if self.faux:
            self.faux.arreter()
        super().tearDown()

    def reglages(self, texte):
        (self.racine / "reglages.local").write_text(texte, encoding="utf-8")

    def mode_reel(self, refus=False, extra=""):
        self.faux = FauxService(refus)
        self.reglages("mode_ia=reel\nCLE_API_GEMINI=cle-de-test\nCLE_API_ANTHROPIC=cle-de-test\n"
                      f"gemini_url={self.faux.url}\nanthropic_url={self.faux.url}\n" + extra)


class TestModeSimule(BaseConnecteurs):

    def test_simule_par_defaut_meme_avec_des_cles(self):
        self.reglages("CLE_API_GEMINI=cle-de-test\nCLE_API_ANTHROPIC=cle-de-test\n")
        self.assertEqual(routeur_ia.mode_ia(), "simule")
        self.assertEqual(list(routeur_ia.fournisseurs_par_defaut()), ["demo"])
        r = routeur_ia.demander_ia("q", "bonjour", difficulte="critique", racine=self.racine)
        self.assertEqual((r["fournisseur"], r["cout_estime"]), ("demo", 0.0))

    def test_mode_reel_sans_rien_de_branche(self):
        self.reglages("mode_ia=reel\n")
        with self.assertRaises(routeur_ia.AucuneIADisponible):
            routeur_ia.demander_ia("q", "bonjour", racine=self.racine)


class TestGemini(BaseConnecteurs):

    def test_courant_non_sensible_va_a_gemini(self):
        self.mode_reel()
        r = routeur_ia.demander_ia("trier", '{"notes": []}', temperature=0.1, racine=self.racine)
        self.assertEqual(r["fournisseur"], "gemini")
        self.assertEqual(r["reponse"], '{"ok": "gemini"}')
        q = self.faux.requetes[0]
        self.assertEqual(q["chemin"], "/v1beta/models/gemini-2.5-flash:generateContent")
        self.assertEqual(q["entetes"].get("x-goog-api-key"), "cle-de-test")
        self.assertEqual(q["corps"]["generationConfig"]["temperature"], 0.1)
        self.assertEqual(q["corps"]["generationConfig"]["responseMimeType"], "application/json")
        self.assertEqual(r["cout_estime"], 0.0)  # offre gratuite

    def test_sensible_jamais_vers_gemini(self):
        self.mode_reel()
        with self.assertRaises(routeur_ia.AucuneIADisponible):
            routeur_ia.demander_ia("q", "secret", sensible=True, racine=self.racine)
        self.assertEqual(self.faux.requetes, [])


class TestClaude(BaseConnecteurs):

    def test_critique_va_a_claude_avec_le_bon_format(self):
        self.mode_reel()
        r = routeur_ia.demander_ia("evaluer", '{"idees": []}', difficulte="critique",
                                   temperature=0.2, date=JOUR_1, racine=self.racine)
        self.assertEqual(r["fournisseur"], "claude")
        self.assertEqual(r["reponse"], "réponse de Claude")
        q = self.faux.requetes[0]
        self.assertEqual(q["chemin"], "/v1/messages")
        self.assertEqual(q["entetes"].get("x-api-key"), "cle-de-test")
        self.assertEqual(q["entetes"].get("anthropic-version"), "2026-10-21")
        self.assertEqual(q["corps"]["model"], "claude-opus-5-5")
        self.assertNotIn("temperature", q["corps"])  # refusée par cette version de l'API
        self.assertEqual(q["corps"]["output_config"], {"effort": "medium"})
        # Prix réel : 1000 jetons × 4 $ + 500 × 20 $ par million = 0,014.
        self.assertAlmostEqual(r["cout_estime"], 0.014)
        self.assertAlmostEqual(routeur_ia.depense_du_mois(JOUR_1, self.racine), 0.014)

    def test_payant_interdit_si_non_autorise(self):
        self.mode_reel()
        r = routeur_ia.demander_ia("q", "x", difficulte="critique", payant_autorise=False,
                                   racine=self.racine)
        self.assertEqual(r["fournisseur"], "gemini")

    def test_plafond_5_euros(self):
        self.mode_reel(extra="BUDGET_IA_MAX_EUR_MOIS=0.01\n")
        with self.assertRaises(routeur_ia.BudgetDepasse):
            routeur_ia.demander_ia("q", "x", difficulte="critique", date=JOUR_1,
                                   racine=self.racine)
        self.assertEqual(self.faux.requetes, [])  # bloqué AVANT d'appeler
        self.assertEqual(routeur_ia.plafond_mensuel(), 0.01)

    def test_refus_de_claude(self):
        self.mode_reel(refus=True)
        with self.assertRaises(RuntimeError):
            routeur_ia.demander_ia("q", "x", difficulte="critique", racine=self.racine)
        self.assertEqual(routeur_ia.depense_du_mois(date.today(), self.racine), 0)


class TestSommeilEnModeReel(BaseConnecteurs):

    def test_sans_ia_disponible_arret_propre(self):
        self.reglages("mode_ia=reel\n")
        projets.creer_projet("A", racine=self.racine)
        cc.creer_note_humaine("A", "Note", "Texte.", date=JOUR_1, racine=self.racine)
        bilan = sommeil.dormir(JOUR_1, projet="A", racine=self.racine)
        self.assertIn("Aucune IA disponible", bilan["arret"])
