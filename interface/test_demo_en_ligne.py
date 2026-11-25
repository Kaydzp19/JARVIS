"""
Tests de la démo en ligne (dossier vercel-demo/, site statique pour Vercel).

1. Les JSON exportés ne contiennent ni chemin local, ni clé, ni contenu de note.
2. La simulation JavaScript des synapses (vercel-demo/js/simulation.js) donne
   EXACTEMENT les mêmes poids que Python (noyau/synapses.py) après 5 nuits.
"""

import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

RACINE_DEPOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE_DEPOT / "exemples"))

import export_demo  # noqa: E402
from noyau.base_tests import TestTemporaire  # noqa: E402

SITE = RACINE_DEPOT / "vercel-demo"
NODE = shutil.which("node")

CHEMINS_LOCAUX = re.compile(r"(/tmp/|/home/|/Users/|/root/|/private/|[A-Za-z]:\\\\|\.jarvis|"
                            r"reglages\.local|file://|projet\.db)")
CLES = re.compile(r"(sk-ant|sk-[A-Za-z0-9]{10,}|AIza[0-9A-Za-z_-]{10,}|CLE_API|api[_-]?key|"
                  r"x-api-key|Bearer\s|COCKPIT_JETON|password|mot de passe\s*[:=])", re.I)


def phrases_des_notes(racine):
    """Les phrases réelles des notes de la démo (hors titres), pour vérifier qu'elles ne fuient pas."""
    from noyau import projets
    phrases = set()
    for p in projets.lister_projets(racine):
        for n in projets.lister_notes(p, racine):
            for ligne in projets.lire_note(p, n["id"], racine).splitlines():
                ligne = re.sub(r"\[\[[^\]]*\]\]", "", ligne).strip(" .:")
                if len(ligne) >= 20 and not ligne.startswith("#"):
                    phrases.add(ligne)
    return phrases


class TestExportSansFuite(TestTemporaire):

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.export = Path(cls._tmp.name) / "data"
        export_demo.exporter(destination=cls.export, bavard=False)

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def fichiers(self):
        # Un export neuf ET les fichiers du dépôt (ceux qui seront publiés).
        return sorted(self.export.glob("*.json")) + sorted((SITE / "data").glob("*.json"))

    def test_fichiers_attendus(self):
        noms = {f.name for f in self.export.glob("*.json")}
        self.assertEqual(noms, {"projets.json", "projet-a.json", "projet-b.json"})
        index = json.loads((self.export / "projets.json").read_text(encoding="utf-8"))
        self.assertEqual([p["nom"] for p in index["projets"]], ["Projet A", "Projet B"])
        a = json.loads((self.export / "projet-a.json").read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(a["notes"]), 10)
        self.assertTrue(a["synapses"] and a["propositions"] and a["journal"])
        self.assertEqual({x["voie"] for x in a["agents"]}, {"planifier", "proposer", "comparer", "verifier"})

    def test_aucun_chemin_local(self):
        for f in self.fichiers():
            m = CHEMINS_LOCAUX.search(f.read_text(encoding="utf-8"))
            self.assertIsNone(m, f"{f.name} : {m.group(0) if m else ''}")

    def test_aucune_cle(self):
        for f in self.fichiers():
            m = CLES.search(f.read_text(encoding="utf-8"))
            self.assertIsNone(m, f"{f.name} : {m.group(0) if m else ''}")

    def test_aucun_contenu_de_note(self):
        racine = Path(self.racine) / "reference"
        racine.mkdir()
        os.environ["DOSSIER_DONNEES"] = str(racine)
        export_demo.preparer_demo(racine)
        phrases = phrases_des_notes(racine)
        self.assertGreater(len(phrases), 10)
        for f in self.fichiers():
            texte = f.read_text(encoding="utf-8")
            self.assertNotIn('"contenu"', texte, f"{f.name} contient un champ « contenu »")
            for phrase in phrases:
                self.assertNotIn(phrase, texte, f"{f.name} contient le texte d'une note")

    def test_la_page_publiee_est_a_jour(self):
        neuve = Path(self.racine) / "cockpit.html"
        export_demo.construire_page(destination=neuve)
        self.assertEqual(neuve.read_text(encoding="utf-8"),
                         (SITE / "cockpit.html").read_text(encoding="utf-8"),
                         "Relance : python3 exemples/export_demo.py")
        page = neuve.read_text(encoding="utf-8")
        for attendu in ("Démo en ligne", "rien n'est enregistré", "js/demo.js", "js/simulation.js",
                        "#030811", "#5CE1FF", "Rajdhani", "JetBrains Mono", "three@0.160.0"):
            self.assertIn(attendu, page)

    def test_vercel_json(self):
        conf = json.loads((RACINE_DEPOT / "vercel.json").read_text(encoding="utf-8"))
        self.assertEqual(conf["outputDirectory"], "vercel-demo")
        self.assertIsNone(conf["framework"])
        self.assertNotIn("buildCommand", conf)
        self.assertTrue(conf["cleanUrls"])              # /cockpit sert cockpit.html

    def test_interface_sphere_publiee_a_jour(self):
        """vercel-demo/ contient exactement l'interface de interface/sphere/, en mode démo en ligne."""
        neuf = Path(self.racine) / "site"
        export_demo.construire_sphere(destination=neuf)
        publies = sorted(f.relative_to(SITE) for f in SITE.rglob("*")
                         if f.is_file() and (f.name == "index.html" or "sphere" in f.relative_to(SITE).parts))
        attendus = sorted(f.relative_to(neuf) for f in neuf.rglob("*") if f.is_file())
        self.assertEqual(publies, attendus, "Relance : python3 exemples/export_demo.py")
        for rel in attendus:
            self.assertEqual((neuf / rel).read_bytes(), (SITE / rel).read_bytes(),
                             f"{rel} n'est pas à jour : relance python3 exemples/export_demo.py")
        index = (SITE / "index.html").read_text(encoding="utf-8")
        for attendu in ('data-mode="demo-en-ligne"', "/sphere/js/main.js", "#010409", "three@0.160.0",
                        "Démo · données fictives"):
            self.assertIn(attendu, index)
        self.assertIn('data-mode="demo-en-ligne"', (SITE / "sphere" / "catalogue.html").read_text(encoding="utf-8"))
        self.assertFalse((SITE / "sphere" / "tests").exists())

    def test_interface_sphere_sans_cle_ni_chemin(self):
        for f in sorted((SITE / "sphere").rglob("*")) + [SITE / "index.html"]:
            if f.is_file():
                texte = f.read_text(encoding="utf-8")
                m = re.search(r"(sk-ant|AIza[0-9A-Za-z_-]{10,}|/Users/|/home/|reglages\.local|projet\.db)", texte)
                self.assertIsNone(m, f"{f.name} : {m.group(0) if m else ''}")


@unittest.skipUnless(NODE, "Node.js absent : comparaison JavaScript impossible")
class TestSimulationJavaScriptIdentiqueAPython(TestTemporaire):

    def simuler_js(self, synapses, reglages, nuits=5):
        script = (
            "const S = require(process.argv[1]);"
            "const d = JSON.parse(require('fs').readFileSync(0, 'utf8'));"
            "for (let i = 0; i < d.nuits; i++) S.appliquerNuits(d.synapses, S.prochaineNuit(d.synapses), d.reglages);"
            "process.stdout.write(JSON.stringify(d.synapses.map(s => [s.id, s.poids, s.archivee, s.jusqu_au])));")
        r = subprocess.run([NODE, "-e", script, str(SITE / "js" / "simulation.js")],
                           input=json.dumps({"synapses": synapses, "reglages": reglages, "nuits": nuits}),
                           capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)
        return {i: (p, a, j) for i, p, a, j in json.loads(r.stdout)}

    def simuler_python(self, projet, nuits=5):
        from noyau import synapses
        for _ in range(nuits):
            synapses.appliquer_oubli(projet, synapses.prochaine_nuit(projet, self.racine),
                                     racine=self.racine)
        return {s["id"]: (s["poids"], bool(s["archivee"]), s["oubli_calcule_jusqu_au"])
                for s in synapses.lister_synapses(projet, self.racine)}

    def comparer(self, projet):
        donnees = export_demo.exporter_projet(projet, self.racine)
        js = self.simuler_js(donnees["synapses"], donnees["reglages"])
        py = self.simuler_python(projet)
        self.assertEqual(set(js), set(py))
        for i in py:
            self.assertAlmostEqual(js[i][0], py[i][0], places=12, msg=f"synapse {i}")
            self.assertEqual(js[i][1:], py[i][1:], f"synapse {i}")
        return py

    def test_demo_apres_5_nuits(self):
        export_demo.preparer_demo(self.racine)
        py = self.comparer("Projet A")
        self.assertTrue(any(p > 0.5 for p, _, _ in py.values()))  # l'apprentissage a joué

    def test_cas_fixe_avec_archivage(self):
        from noyau import corps_calleux as cc
        from noyau import projets, synapses
        projets.creer_projet("Cas fixe", racine=self.racine)
        n = lambda t, x: cc.creer_note_humaine("Cas fixe", t, x, date="2027-01-01", racine=self.racine)
        x = n("X", "Voir [[Y]].")
        y = n("Y", "Voir [[Z]].")
        z = n("Z", "Voir [[X]].")
        # Poids de départ connus : X→Y presque oublié, Y→Z utilisé deux jours, Z→X neutre.
        db = projets.dossier_projet("Cas fixe", self.racine) / "projet.db"
        with sqlite3.connect(db) as c:
            c.execute("UPDATE synapses SET poids = 0.052 WHERE note_source = ? AND note_cible = ?", (x, y))
            c.execute("UPDATE synapses SET poids = 0.3 WHERE note_source = ? AND note_cible = ?", (y, z))
        c.close()
        for jour in ("2027-01-01", "2027-01-03"):
            synapses.utiliser_ensemble("Cas fixe", y, z, jour, racine=self.racine)
        py = self.comparer("Cas fixe")
        xy = synapses.synapse_entre("Cas fixe", x, y, racine=self.racine)
        self.assertTrue(xy["archivee"])                      # 0,052 × 0,98² < 0,05
        yz = synapses.synapse_entre("Cas fixe", y, z, racine=self.racine)
        attendu = 0.3
        for servi in (1, 0, 1, 0, 0):
            attendu = 0.98 * attendu + 0.10 * servi
        self.assertAlmostEqual(yz["poids"], attendu, places=12)
        self.assertEqual(len(py), 3)
