"""
Tests de la partie JavaScript de l'interface « sphère » (Node.js, si présent).

1. Les tests unitaires JavaScript (interface/sphere/tests/*.test.mjs) : contrat
   d'affichage, application des événements, source de démonstration, bilan de nuit.
2. Parité Python ↔ JavaScript : le schéma des événements et le routage par code
   donnent exactement les mêmes résultats des deux côtés.
"""

import json
import shutil
import subprocess
import unittest
from pathlib import Path

from interface import conversation
from noyau import affichage
from noyau.base_tests import TestTemporaire

DOSSIER = Path(__file__).resolve().parent / "sphere"
NODE = shutil.which("node")


def node(script, entree):
    r = subprocess.run([NODE, "--input-type=module", "-e", script], input=json.dumps(entree),
                       capture_output=True, text=True, timeout=60, cwd=str(DOSSIER))
    if r.returncode != 0:
        raise AssertionError(r.stderr)
    return json.loads(r.stdout)


@unittest.skipUnless(NODE, "Node.js absent : tests JavaScript non lancés")
class TestJavaScript(TestTemporaire):

    def test_tests_unitaires_javascript(self):
        fichiers = sorted(str(f) for f in (DOSSIER / "tests").glob("*.test.mjs"))
        self.assertGreaterEqual(len(fichiers), 3)
        r = subprocess.run([NODE, "--test", *fichiers], capture_output=True, text=True, timeout=120)
        self.assertEqual(r.returncode, 0, r.stdout[-3000:] + r.stderr[-2000:])
        self.assertIn("# fail 0", r.stdout)

    def test_parite_du_schema(self):
        base = {"scene": "graphique", "titre": "Dépenses", "donnees": {"serie": [1]}}
        cas = [base, dict(base, scene="inconnue_x"), dict(base, scene="Mauvais"), dict(base, titre=""),
               dict(base, donnees={"notes": [{"contenu": "x"}]}), dict(base, donnees={"a": {"Extrait": 1}}),
               dict(base, controles={"periode": ["7 j", "6 mois"]}), dict(base, controles={"periode": ["1 an"]}),
               dict(base, controles={"zoom": ["x"]}), dict(base, actions=[{"id": "voir", "libelle": "Voir"}]),
               dict(base, actions=[{"id": "voir", "libelle": ""}]), dict(base, projet="*",
                                                                         actions=[{"id": "publier", "libelle": "P"}]),
               dict(base, projet="*"), dict(base, fermeture=0), dict(base, fermeture=900), dict(base, inconnu=1),
               dict(base, actions=[{"id": "a", "libelle": "x", "type": "magie"}]), "texte", [1, 2]]
        js = node("import { valider } from './js/widgets/contrat.js';"
                  "let d='';process.stdin.on('data',c=>d+=c).on('end',()=>{"
                  "console.log(JSON.stringify(JSON.parse(d).map(e=>valider(e).length===0)));});", cas)
        self.assertEqual(js, [affichage.valider(e) == [] for e in cas])

    def test_parite_du_routage(self):
        phrases = ["État de ma machine", "cpu ?", "Va-t-il pleuvoir demain ?", "Météo", "Résumé de la nuit",
                   "Combien coûte l'IA ce mois ?", "Graphique de mes dépenses", "Ouvre la note Budget",
                   "montre-moi la note Offre !", "Que sais-tu du lancement ?", "Où en sont mes projets ?",
                   "ma batterie", "le plafond", "Planification", "Mes tâches de demain",
                   "Qu'est-ce que j'ai aujourd'hui ?", "mon agenda de la semaine", "un rendez-vous"]
        js = node("import { routerReel } from './js/donnees.js';"
                  "let d='';process.stdin.on('data',c=>d+=c).on('end',()=>{"
                  "console.log(JSON.stringify(JSON.parse(d).map(routerReel)));});", phrases)
        self.assertEqual(js, [conversation.router(p) for p in phrases])

    def test_parite_de_la_recurrence(self):
        from noyau import planification
        cas = [["2027-01-01", "jours_ouvres"], ["2027-01-31", "mensuelle"], ["2028-01-31", "mensuelle"],
               ["2027-12-29", "quotidienne"], ["2027-02-26", "hebdomadaire"], ["2027-01-02", "jours_ouvres"]]
        js = node("import { suite } from './js/planification.js';"
                  "let d='';process.stdin.on('data',c=>d+=c).on('end',()=>{"
                  "console.log(JSON.stringify(JSON.parse(d).map(([a,r])=>{const l=[];"
                  "for(const x of suite(a,r)){l.push(x);if(l.length>=8)break;}return l;})));});", cas)
        py = []
        for a, r in cas:
            it = planification.suite(a, r)
            py.append([next(it).isoformat() for _ in range(8)])
        self.assertEqual(js, py)
